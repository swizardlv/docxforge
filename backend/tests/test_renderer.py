"""Tests for DefaultRenderer."""

from __future__ import annotations

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
    assert items[0].type == "image"
    assert items[0].props["src"] == "/path/to/img.png"
    assert items[0].props["alt"] == "说明"
