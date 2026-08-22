"""Tests for DefaultRenderer."""

from __future__ import annotations

from pathlib import Path

from docxforge.core.renderer import DefaultRenderer
from docxforge.models import DocumentAST, HeadingNode, ParagraphNode, StyleMap


def test_renderer_build_commands() -> None:
    renderer = DefaultRenderer()
    ast = DocumentAST(
        nodes=[
            HeadingNode(level=1, content="标题1"),
            ParagraphNode(content="正文段落"),
        ]
    )
    style_map = StyleMap()
    items = renderer.build_commands(ast, style_map)

    assert len(items) == 2
    assert items[0].command == "add"
    assert items[0].props["text"] == "标题1"
    assert items[1].props["text"] == "正文段落"


def test_renderer_image_node() -> None:
    from docxforge.models import ImageNode

    renderer = DefaultRenderer()
    ast = DocumentAST(nodes=[ImageNode(src="/path/to/img.png", alt="说明")])
    items = renderer.build_commands(ast, StyleMap())

    assert len(items) == 1
    assert items[0].command == "add"
    assert items[0].type == "picture"
    assert items[0].props["src"] == "/path/to/img.png"
    assert items[0].props["alt"] == "说明"


def test_resolve_image_base64(tmp_path: Path) -> None:
    from docxforge.core.renderer import resolve_image_source

    b64_src = (
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="  # noqa: E501
    )
    res = resolve_image_source(b64_src, workdir=tmp_path)

    resolved_path = Path(res)
    assert resolved_path.exists()
    assert resolved_path.suffix == ".png"


def test_resolve_image_relative_path(tmp_path: Path) -> None:
    from docxforge.core.renderer import resolve_image_source

    img_dir = tmp_path / "assets"
    img_dir.mkdir()
    real_img = img_dir / "test.jpg"
    real_img.write_text("dummy image content", encoding="utf-8")

    res = resolve_image_source("assets/test.jpg", base_dir=tmp_path)
    assert res == str(real_img.resolve())


def test_renderer_heading_uses_style_map() -> None:
    """Custom style_map.headings dict must be honoured, not getattr default."""
    renderer = DefaultRenderer()
    sm = StyleMap()
    sm.headings[1] = "CustomH1"
    ast = DocumentAST(nodes=[HeadingNode(level=1, content="Test")])
    items = renderer.build_commands(ast, sm)
    assert items[0].props["style"] == "CustomH1"


def test_renderer_table_cell_fill() -> None:
    from docxforge.models import TableNode

    renderer = DefaultRenderer()
    sm = StyleMap()
    ast = DocumentAST(
        nodes=[
            TableNode(
                headers=["A", "B"],
                rows=[["1", "2"], ["3", "4"]],
            )
        ]
    )
    items = renderer.build_commands(ast, sm)
    # add table + header row set + 6 cell sets = 8 commands
    assert len(items) == 8
    assert items[0].command == "add"
    assert items[0].type == "table"
    assert items[0].props["rows"] == "3"
    assert items[0].props["cols"] == "2"
    # header row cell sets
    assert items[2].path == "/body/tbl[1]/tr[1]/tc[1]"
    assert items[2].props["text"] == "A"
    assert items[3].path == "/body/tbl[1]/tr[1]/tc[2]"
    assert items[3].props["text"] == "B"
    # data row 1 cell sets
    assert items[4].path == "/body/tbl[1]/tr[2]/tc[1]"
    assert items[4].props["text"] == "1"
    # data row 2 cell sets
    assert items[6].path == "/body/tbl[1]/tr[3]/tc[1]"
    assert items[6].props["text"] == "3"


def test_renderer_quote_node() -> None:
    from docxforge.models import QuoteNode

    renderer = DefaultRenderer()
    ast = DocumentAST(nodes=[QuoteNode(content="引用")])
    items = renderer.build_commands(ast, StyleMap())
    assert len(items) == 1
    assert items[0].command == "add"
    assert items[0].type == "paragraph"
    assert items[0].props["text"] == "引用"
    assert items[0].props["style"] == "Quote"


def test_renderer_pagebreak_node() -> None:
    from docxforge.models import PageBreakNode

    renderer = DefaultRenderer()
    ast = DocumentAST(nodes=[PageBreakNode()])
    items = renderer.build_commands(ast, StyleMap())
    assert len(items) == 1
    assert items[0].command == "add"
    assert items[0].type == "pagebreak"
    assert items[0].props["type"] == "page"


def test_renderer_nested_list_numlevel() -> None:
    from docxforge.models import ListItem, ListNode

    renderer = DefaultRenderer()
    ast = DocumentAST(
        nodes=[
            ListNode(
                ordered=False,
                items=[
                    ListItem(content="top", level=0),
                    ListItem(content="nested", level=1),
                ],
            )
        ]
    )
    items = renderer.build_commands(ast, StyleMap())
    assert len(items) == 2
    # Top-level item: no listStyle / numLevel
    assert items[0].props["text"] == "top"
    assert "numLevel" not in items[0].props
    # Nested item: listStyle + numLevel
    assert items[1].props["text"] == "nested"
    assert items[1].props["listStyle"] == "bullet"
    assert items[1].props["numLevel"] == "1"
