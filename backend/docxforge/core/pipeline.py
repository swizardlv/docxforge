"""End-to-end rendering pipeline orchestration implementation."""

from __future__ import annotations

import time
from pathlib import Path

from docxforge.config import Settings, get_settings
from docxforge.core.assembler import DefaultDocumentAssembler
from docxforge.core.markdown_ast import DefaultMarkdownParser
from docxforge.core.officecli import DefaultOfficeCLIRunner
from docxforge.core.renderer import DefaultRenderer
from docxforge.core.template import DefaultTemplateEngine
from docxforge.errors import RenderError
from docxforge.interfaces import (
    DocumentAssembler,
    MarkdownParser,
    OfficeCLIRunner,
    Renderer,
    TemplateEngine,
)
from docxforge.models import BatchItem, RenderRequest, RenderResult


class DefaultRenderPipeline:
    """Production implementation of RenderPipeline Protocol."""

    def __init__(
        self,
        settings: Settings | None = None,
        runner: OfficeCLIRunner | None = None,
        template_engine: TemplateEngine | None = None,
        parser: MarkdownParser | None = None,
        renderer: Renderer | None = None,
        assembler: DocumentAssembler | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.runner = runner or DefaultOfficeCLIRunner(self.settings)
        self.template_engine = template_engine or DefaultTemplateEngine(self.settings, self.runner)
        self.parser = parser or DefaultMarkdownParser()
        self.renderer = renderer or DefaultRenderer()
        self.assembler = assembler or DefaultDocumentAssembler()

    def render(self, request: RenderRequest, *, workdir: Path, job_id: str) -> RenderResult:
        start_time = time.perf_counter()
        output_file = workdir / f"{job_id}.docx"

        try:
            # 1. Prepare base document
            prepared = self.template_engine.prepare_base(request.template_id, output_file)

            # 2. Parse Markdown (also used for the fast_markdown source file)
            ast = self.parser.parse(
                request.markdown,
                template_id=request.template_id,
            )

            # 3. Resolve StyleMap and build body commands
            style_map = self.template_engine.style_map_for(request.template_id)

            if request.options.fast_markdown:
                # Native officecli markdown expansion: faster but lossy
                # (links/images degrade to plain text). The source file lives
                # in the ephemeral job sandbox and is shredded with the job.
                md_source = workdir / f"{job_id}.md"
                md_source.write_text(request.markdown, encoding="utf-8")
                body_items = [
                    BatchItem(
                        command="add",
                        parent="/",
                        type="markdown",
                        props={"src": str(md_source)},
                    )
                ]
            else:
                # Count existing tables in the base document so the renderer
                # can correctly index new tables past them (removing template
                # content renumbers tbl[N] indices, but retained cover tables
                # still occupy the first N slots).
                try:
                    table_offset = len(self.runner.query(output_file, "table"))
                except Exception:
                    table_offset = 0
                body_items = self.renderer.build_commands(
                    ast,
                    style_map,
                    parent="/body",
                    workdir=workdir,
                    base_dir=request.base_dir,
                    table_offset=table_offset,
                )

            # 4. Build assembler commands. Cover and TOC run BEFORE the body so
            #    the appended TOC lands between the cover section and the body
            #    content, not at the end of the document.
            assembler_items: list[BatchItem] = []

            # Merge template-level cover overrides (from the preview panel)
            # into the per-request replacements. doc_title mode uses the file's
            # effective title (request.doc_title or markdown first H1).
            # Per-request replacements always win over template presets.
            merged_replacements = dict(request.cover.replacements)
            if request.template_id:
                try:
                    effective_title = request.doc_title or ast.doc_title or ""
                    for o in self.template_engine.cover_overrides(request.template_id):
                        if not o.find:
                            continue
                        if o.mode.value == "doc_title":
                            merged_replacements.setdefault(o.find, effective_title)
                        elif o.replace is not None:
                            merged_replacements.setdefault(o.find, o.replace)
                except Exception:
                    pass

            if request.cover.enabled and merged_replacements:
                merged_cover = request.cover.model_copy(
                    update={"replacements": merged_replacements}
                )
                assembler_items.extend(self.assembler.cover_commands(merged_cover, prepared))
            if request.toc.enabled:
                assembler_items.extend(self.assembler.toc_commands(request.toc, prepared))

            update_fields = (
                request.options.update_fields
                if request.options
                else self.settings.update_fields_on_open
            )
            assembler_items.extend(self.assembler.settings_commands(update_fields=update_fields))

            if request.header_footer.header_text or request.header_footer.footer_text:
                assembler_items.extend(
                    self.assembler.header_footer_commands(request.header_footer, prepared)
                )

            # 5. Combine and execute batch. Resident mode keeps the document in
            #    officecli's memory for one open/save cycle (speed). Either way
            #    we close at the end: `close` flushes any resident (from
            #    `create`/`open`) to disk and releases it, so non-officecli
            #    readers always see the finished file and the sandbox shredder
            #    cannot be undone by a deferred write. It is a no-op when no
            #    resident is active.
            all_items = assembler_items + body_items
            warnings: list[str] = []
            if request.options.use_resident:
                self.runner.open(output_file)
            try:
                if all_items:
                    self.runner.batch(output_file, all_items)
                if request.options.validate_output:
                    issues = self.runner.validate(output_file)
                    if issues:
                        warnings.append(f"OpenXML 校验发现 {len(issues)} 个问题")
                        warnings.extend(issues[:5])
            finally:
                # Best-effort flush: never mask the original batch failure.
                try:
                    self.runner.close(output_file)
                except Exception:
                    pass

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            return RenderResult(
                job_id=job_id,
                filename=request.filename or f"{job_id}.docx",
                output_path=output_file,
                elapsed_ms=elapsed_ms,
                command_count=len(all_items),
                node_count=len(ast.nodes),
                warnings=warnings,
            )

        except Exception as exc:
            if isinstance(exc, RenderError):
                raise exc
            # Preserve the underlying officecli stderr (e.g. the failing batch
            # command) so the API error response is actionable.
            detail = getattr(exc, "detail", None) or str(exc)
            raise RenderError(f"Render failed for job {job_id}: {exc}", detail=detail) from exc
