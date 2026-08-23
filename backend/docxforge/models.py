"""Shared data contracts.

This module is the single source of truth for every DTO crossing a module
boundary (parser -> renderer -> pipeline -> API -> frontend). Changing a field
here is a cross-team change: announce it before editing.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Markdown AST
# ---------------------------------------------------------------------------


class NodeType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    CODE = "code"
    QUOTE = "quote"
    IMAGE = "image"
    PAGE_BREAK = "pagebreak"
    THEMATIC_BREAK = "thematic_break"


class BaseNode(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HeadingNode(BaseNode):
    type: Literal[NodeType.HEADING] = NodeType.HEADING
    level: int = Field(ge=1, le=6)
    content: str


class ParagraphNode(BaseNode):
    type: Literal[NodeType.PARAGRAPH] = NodeType.PARAGRAPH
    content: str


class ListItem(BaseNode):
    content: str
    #: 0 = top level. Nested items keep their own depth.
    level: int = Field(default=0, ge=0)


class ListNode(BaseNode):
    type: Literal[NodeType.LIST] = NodeType.LIST
    ordered: bool = False
    start: int = 1
    items: list[ListItem] = Field(default_factory=list)


class TableNode(BaseNode):
    type: Literal[NodeType.TABLE] = NodeType.TABLE
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    caption: str | None = None


class CodeNode(BaseNode):
    type: Literal[NodeType.CODE] = NodeType.CODE
    content: str
    language: str | None = None


class QuoteNode(BaseNode):
    type: Literal[NodeType.QUOTE] = NodeType.QUOTE
    content: str


class ImageNode(BaseNode):
    type: Literal[NodeType.IMAGE] = NodeType.IMAGE
    src: str
    alt: str | None = None


class PageBreakNode(BaseNode):
    type: Literal[NodeType.PAGE_BREAK] = NodeType.PAGE_BREAK


class ThematicBreakNode(BaseNode):
    type: Literal[NodeType.THEMATIC_BREAK] = NodeType.THEMATIC_BREAK


ASTNode = Annotated[
    HeadingNode
    | ParagraphNode
    | ListNode
    | TableNode
    | CodeNode
    | QuoteNode
    | ImageNode
    | PageBreakNode
    | ThematicBreakNode,
    Field(discriminator="type"),
]


class DocumentAST(BaseModel):
    """The Internal Python DTO described in PRD section 5."""

    model_config = ConfigDict(extra="forbid")

    doc_title: str | None = None
    template_id: str | None = None
    nodes: list[ASTNode] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Style mapping
# ---------------------------------------------------------------------------


class StyleMap(BaseModel):
    """Maps AST node kinds to Word style ids (PRD section 4, module B)."""

    model_config = ConfigDict(extra="forbid")

    headings: dict[int, str] = Field(
        default_factory=lambda: {
            1: "Heading1",
            2: "Heading2",
            3: "Heading3",
            4: "Heading4",
            5: "Heading5",
            6: "Heading6",
        }
    )
    paragraph: str = "Normal"
    list_ordered: str = "ListNumber"
    list_bullet: str = "ListBullet"
    quote: str = "Quote"
    code: str = "HTMLPreformatted"
    caption: str = "Caption"
    table: str = "TableGrid"
    title: str = "Title"

    def heading(self, level: int) -> str:
        return self.headings.get(level, self.headings.get(1, "Heading1"))


# ---------------------------------------------------------------------------
# OfficeCLI batch protocol
# ---------------------------------------------------------------------------


class BatchItem(BaseModel):
    """One entry of an ``officecli batch`` JSON array.

    Field names mirror the CLI exactly. ``to_payload`` drops unset keys so the
    emitted JSON stays minimal and replayable.
    """

    model_config = ConfigDict(extra="forbid")

    command: str
    parent: str | None = None
    path: str | None = None
    type: str | None = None
    props: dict[str, str] = Field(default_factory=dict)
    after: str | None = None
    before: str | None = None
    index: int | None = None
    selector: str | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    part: str | None = None
    xpath: str | None = None
    action: str | None = None
    xml: str | None = None

    def to_payload(self) -> dict[str, Any]:
        data = self.model_dump(by_alias=True, exclude_none=True)
        if not data.get("props"):
            data.pop("props", None)
        return data


class BatchOutcome(BaseModel):
    """Result summary of an ``officecli batch`` run."""

    model_config = ConfigDict(extra="allow")

    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    rolled_back: bool = False
    warnings: list[str] = Field(default_factory=list)
    raw: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class StyleInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    style_id: str
    name: str | None = None
    type: str | None = None
    based_on: str | None = None
    font: str | None = None
    size_pt: float | None = None
    #: Extended format properties (extracted from w:rPr sub-commands).
    color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    line_spacing: str | None = None
    alignment: str | None = None


class TemplateInfo(BaseModel):
    """Serialized as ``template_config.json`` (PRD section 4, module A)."""

    model_config = ConfigDict(extra="forbid")

    template_id: str
    name: str
    source_path: Path | None = None
    styles: list[StyleInfo] = Field(default_factory=list)
    style_map: StyleMap = Field(default_factory=StyleMap)
    has_numbering: bool = False
    has_theme: bool = False
    has_cover: bool = False
    cover_paragraph_count: int = 0
    page_count_hint: int | None = None
    created_at: datetime | None = None
    warnings: list[str] = Field(default_factory=list)


class PreparedBase(BaseModel):
    """A template-derived working document, ready for body content."""

    model_config = ConfigDict(extra="forbid")

    path: Path
    template_id: str | None = None
    #: Body paragraphs kept from the template (the cover section).
    cover_paragraph_count: int = 0
    #: True when the template body was cleared of sample content.
    body_cleared: bool = False
    #: The template already carries header/footer parts. When true the
    #: assembler must update the existing part instead of adding a new one
    #: (officecli rejects a second 'default' header/footer in one section).
    has_header: bool = False
    has_footer: bool = False
    style_map: StyleMap = Field(default_factory=StyleMap)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Render request / result
# ---------------------------------------------------------------------------


class TocOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    levels: str = "1-3"
    title: str | None = "目录"
    hyperlinks: bool = True
    page_numbers: bool = True
    #: Insert a page break between the TOC and the body.
    page_break_after: bool = True


class CoverOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    #: ``find -> replace`` pairs applied to the template cover section.
    replacements: dict[str, str] = Field(default_factory=dict)
    #: Insert a page break after the cover section.
    page_break_after: bool = True


class HeaderFooterOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    header_text: str | None = None
    footer_text: str | None = None
    page_numbers: bool = True
    #: Skip header/footer on the cover page.
    different_first_page: bool = True


class RenderOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Use OfficeCLI's native ``--type markdown`` expansion instead of the
    #: AST -> batch path. Faster, but lossy (no links/images, plain cells).
    fast_markdown: bool = False
    update_fields: bool = True
    validate_output: bool = False
    #: Keep the officecli resident process warm across the render.
    use_resident: bool = True


class RenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str
    doc_title: str | None = None
    template_id: str | None = None
    toc: TocOptions = Field(default_factory=TocOptions)
    cover: CoverOptions = Field(default_factory=CoverOptions)
    header_footer: HeaderFooterOptions = Field(default_factory=HeaderFooterOptions)
    options: RenderOptions = Field(default_factory=RenderOptions)
    #: Output filename stem; the pipeline always writes ``.docx``.
    filename: str | None = None
    #: Base directory for resolving local relative image paths.
    base_dir: str | None = None


class RenderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    filename: str
    output_path: Path
    elapsed_ms: int
    command_count: int = 0
    node_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


# ---------------------------------------------------------------------------
# Jobs / sandbox
# ---------------------------------------------------------------------------


class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    READY = "ready"
    DESTROYED = "destroyed"
    FAILED = "failed"


class JobInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    state: JobState = JobState.PENDING
    filename: str | None = None
    created_at: datetime
    expires_at: datetime | None = None
    destroyed_at: datetime | None = None
    ttl_seconds: int = 60
    elapsed_ms: int | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None

    @property
    def seconds_remaining(self) -> int:
        if self.expires_at is None:
            return 0
        delta = (self.expires_at - datetime.now(self.expires_at.tzinfo)).total_seconds()
        return max(0, int(delta))


class DestroyReport(BaseModel):
    """Evidence for DoD #3 - zero data remnants."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    destroyed: bool
    files_shredded: int = 0
    bytes_shredded: int = 0
    sandbox_path: Path | None = None
    sandbox_exists_after: bool = False
    destroyed_at: datetime | None = None


# ---------------------------------------------------------------------------
# API envelopes
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"] = "ok"
    version: str
    officecli_available: bool
    officecli_version: str | None = None
    officecli_path: str | None = None
    sandbox_root: Path
    sandbox_is_memory_backed: bool = False
    job_ttl_seconds: int = 60


class TemplateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    templates: list[TemplateInfo] = Field(default_factory=list)


class StyleRole(str, Enum):
    UNUSED = "unused"
    HEADING1 = "heading1"
    HEADING2 = "heading2"
    HEADING3 = "heading3"
    HEADING4 = "heading4"
    HEADING5 = "heading5"
    HEADING6 = "heading6"
    PARAGRAPH = "paragraph"
    LIST_ORDERED = "list_ordered"
    LIST_BULLET = "list_bullet"
    QUOTE = "quote"
    CODE = "code"
    CAPTION = "caption"
    TABLE = "table"
    TITLE = "title"


class StyleEntry(BaseModel):
    """One style in the style-list response, annotated with its inferred role."""

    model_config = ConfigDict(extra="forbid")

    style_id: str
    name: str | None = None
    type: str | None = None
    font: str | None = None
    size_pt: float | None = None
    color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    line_spacing: str | None = None
    alignment: str | None = None
    role: StyleRole = StyleRole.UNUSED


class TemplateStylesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    styles: list[StyleEntry] = Field(default_factory=list)
    style_map: StyleMap = Field(default_factory=StyleMap)


class RenderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    filename: str
    download_url: str
    elapsed_ms: int
    expires_at: datetime | None = None
    ttl_seconds: int = 60
    warnings: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    detail: str | None = None
