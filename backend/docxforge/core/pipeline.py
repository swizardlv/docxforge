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

            # 2. Parse Markdown
            ast = self.parser.parse(
                request.markdown,
                template_id=request.template_id,
            )

            # 3. Resolve StyleMap and build body commands
            style_map = self.template_engine.style_map_for(request.template_id)
            body_items = self.renderer.build_commands(
                ast,
                style_map,
                parent="/body",
                workdir=workdir,
                base_dir=request.base_dir,
            )

            # 4. Build assembler commands
            assembler_items: list[BatchItem] = []
            if request.cover:
                assembler_items.extend(self.assembler.cover_commands(request.cover, prepared))

            if request.toc:
                assembler_items.extend(self.assembler.toc_commands(request.toc, prepared))

            if request.header_footer:
                assembler_items.extend(
                    self.assembler.header_footer_commands(request.header_footer, prepared)
                )

            update_fields = (
                request.options.update_fields
                if request.options
                else self.settings.update_fields_on_open
            )
            assembler_items.extend(self.assembler.settings_commands(update_fields=update_fields))

            # 5. Combine and execute batch
            all_items = body_items + assembler_items
            if all_items:
                self.runner.batch(output_file, all_items)

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            return RenderResult(
                job_id=job_id,
                filename=request.filename or f"{job_id}.docx",
                output_path=output_file,
                elapsed_ms=elapsed_ms,
                command_count=len(all_items),
                node_count=len(ast.nodes),
                warnings=[],
            )

        except Exception as exc:
            if isinstance(exc, RenderError):
                raise exc
            raise RenderError(f"Render failed for job {job_id}: {exc}") from exc
