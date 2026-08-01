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
