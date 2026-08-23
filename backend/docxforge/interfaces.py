"""Structural interfaces between DocXForge modules.

These are ``typing.Protocol`` definitions, not base classes: implementations
do not import or subclass them, they just match the shape. Consumers type
their dependencies against these protocols so modules can be built and tested
in parallel and swapped for fakes.

Ownership map (see docs/CONTRACTS.md):
  - OfficeCLIRunner, TemplateEngine  -> core/officecli.py, core/template.py
  - MarkdownParser, Renderer, DocumentAssembler, RenderPipeline
                                     -> core/markdown_ast.py, core/renderer.py,
                                        core/assembler.py, core/pipeline.py
  - Sandbox, JobStore                -> core/sandbox.py, api/jobs.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from docxforge.models import (
    BatchItem,
    BatchOutcome,
    CoverOptions,
    DestroyReport,
    DocumentAST,
    HeaderFooterOptions,
    JobInfo,
    PreparedBase,
    RenderRequest,
    RenderResult,
    StyleMap,
    TemplateInfo,
    TocOptions,
)


@runtime_checkable
class OfficeCLIRunner(Protocol):
    """Thin, typed wrapper around the ``officecli`` binary (PRD task 1)."""

    def version(self) -> str:
        """Return the officecli semantic version, e.g. ``1.0.143``."""

    def is_available(self) -> bool:
        """True when the binary is resolvable and executable."""

    def create(self, doc: Path, *, locale: str | None = None, minimal: bool = False) -> None:
        """Create a blank document at ``doc``."""

    def add(
        self,
        doc: Path,
        parent: str,
        *,
        type: str,
        props: dict[str, str] | None = None,
        after: str | None = None,
        before: str | None = None,
        index: int | None = None,
    ) -> str:
        """Add an element; returns the path of the created node."""

    def set(
        self,
        doc: Path,
        path: str,
        *,
        props: dict[str, str] | None = None,
        find: str | None = None,
        replace: str | None = None,
    ) -> None:
        """Set properties, or find/replace text within ``path``'s scope."""

    def get(self, doc: Path, path: str = "/", *, depth: int | None = None) -> dict[str, Any]:
        """Read a node as structured JSON."""

    def query(self, doc: Path, selector: str) -> list[dict[str, Any]]:
        """Run a CSS-like selector query."""

    def remove(self, doc: Path, path: str) -> None:
        """Remove an element."""

    def view(self, doc: Path, mode: str = "outline", *, extra_args: list[str] | None = None) -> str:
        """Render a view mode (outline / text / stats / issues / html)."""

    def dump(self, doc: Path, path: str = "/", *, out: Path | None = None) -> list[dict[str, Any]]:
        """Serialize a subtree into replayable batch JSON."""

    def batch(
        self,
        doc: Path,
        items: list[BatchItem],
        *,
        best_effort: bool = False,
        stop_on_error: bool = False,
    ) -> BatchOutcome:
        """Execute many commands in one open/save cycle."""

    def raw_set(self, doc: Path, part: str, *, xpath: str, action: str, xml: str) -> None:
        """L3 escape hatch for raw OOXML edits."""

    def validate(self, doc: Path) -> list[str]:
        """Validate against the OpenXML schema; returns issue strings."""

    def open(self, doc: Path) -> None:
        """Start a resident session to keep the document in memory."""

    def save(self, doc: Path) -> None:
        """Flush pending in-memory changes to disk, keeping the resident."""

    def close(self, doc: Path) -> None:
        """Flush and stop the resident session. Required before non-officecli reads."""


@runtime_checkable
class TemplateEngine(Protocol):
    """Template extraction and base-document preparation (PRD task 3)."""

    def register_from_docx(
        self, source: Path, *, name: str | None = None, template_id: str | None = None
    ) -> TemplateInfo:
        """Ingest a reference ``.docx`` and persist its template_config.json."""

    def list_templates(self) -> list[TemplateInfo]: ...

    def get_template(self, template_id: str) -> TemplateInfo:
        """Raises TemplateNotFoundError when unknown."""

    def delete_template(self, template_id: str) -> None: ...

    def prepare_base(self, template_id: str | None, dest: Path) -> PreparedBase:
        """Produce a working document at ``dest``.

        With a template: clone it, keep styles/numbering/theme/section and the
        cover section, clear sample body content. Without one: a blank docx.
        """

    def style_map_for(self, template_id: str | None) -> StyleMap:
        """Resolve the node-kind -> Word style mapping, honoring template styles."""

    def cover_overrides(self, template_id: str) -> list:
        """Cover field replacements configured for the template (fixed/doc_title)."""


@runtime_checkable
class MarkdownParser(Protocol):
    """Markdown -> DocumentAST (PRD task 2)."""

    def parse(
        self, markdown: str, *, doc_title: str | None = None, template_id: str | None = None
    ) -> DocumentAST: ...


@runtime_checkable
class Renderer(Protocol):
    """DocumentAST -> officecli batch commands (PRD task 2)."""

    def build_commands(
        self,
        ast: DocumentAST,
        style_map: StyleMap,
        *,
        parent: str = "/body",
    ) -> list[BatchItem]: ...


@runtime_checkable
class DocumentAssembler(Protocol):
    """Cover / TOC / header / footer / settings injection (PRD task 4)."""

    def cover_commands(self, options: CoverOptions, base: PreparedBase) -> list[BatchItem]: ...

    def toc_commands(self, options: TocOptions, base: PreparedBase) -> list[BatchItem]: ...

    def header_footer_commands(
        self, options: HeaderFooterOptions, base: PreparedBase
    ) -> list[BatchItem]: ...

    def settings_commands(self, *, update_fields: bool) -> list[BatchItem]: ...


@runtime_checkable
class RenderPipeline(Protocol):
    """End-to-end orchestration: markdown in, .docx on disk out."""

    def render(self, request: RenderRequest, *, workdir: Path, job_id: str) -> RenderResult: ...


@runtime_checkable
class Sandbox(Protocol):
    """Ephemeral per-job scratch space with physical destruction (PRD module D)."""

    def create(self, job_id: str) -> Path:
        """Create and return the job's scratch directory."""

    def path_for(self, job_id: str) -> Path: ...

    def exists(self, job_id: str) -> bool: ...

    def destroy(self, job_id: str) -> DestroyReport:
        """Overwrite then unlink every file, remove the directory."""

    def destroy_expired(self) -> list[DestroyReport]:
        """Sweep jobs past their TTL. Called by the reaper loop."""


@runtime_checkable
class JobStore(Protocol):
    """Job lifecycle bookkeeping backing the API layer."""

    def create_job(self, *, ttl_seconds: int | None = None) -> JobInfo: ...

    def get_job(self, job_id: str) -> JobInfo:
        """Raises JobNotFoundError / JobExpiredError."""

    def list_jobs(self) -> list[JobInfo]: ...

    def mark_ready(self, job_id: str, result: RenderResult) -> JobInfo: ...

    def mark_failed(self, job_id: str, error: str) -> JobInfo: ...

    def destroy_job(self, job_id: str) -> DestroyReport: ...
