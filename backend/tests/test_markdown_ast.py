"""Tests for DefaultMarkdownParser."""

from __future__ import annotations

from docxforge.core.markdown_ast import DefaultMarkdownParser
from docxforge.models import HeadingNode, ListNode, ParagraphNode, TableNode


def test_parse_markdown_basic(sample_markdown: str) -> None:
    parser = DefaultMarkdownParser()
    ast = parser.parse(sample_markdown)

    assert ast.doc_title == "一、 项目背景与需求分析"
    assert len(ast.nodes) > 0

    headings = [node for node in ast.nodes if isinstance(node, HeadingNode)]
    assert len(headings) >= 3

    paragraphs = [node for node in ast.nodes if isinstance(node, ParagraphNode)]
    assert len(paragraphs) >= 1

    lists = [node for node in ast.nodes if isinstance(node, ListNode)]
    assert len(lists) >= 2

    tables = [node for node in ast.nodes if isinstance(node, TableNode)]
    assert len(tables) == 1
    assert len(tables[0].headers) == 3


def test_parse_markdown_image() -> None:
    parser = DefaultMarkdownParser()
    md = "# 架构图\n\n![系统架构示意图](https://example.com/arch.png)\n"
    ast = parser.parse(md)

    from docxforge.models import ImageNode

    images = [node for node in ast.nodes if isinstance(node, ImageNode)]
    assert len(images) == 1
    assert images[0].src == "https://example.com/arch.png"
    assert images[0].alt == "系统架构示意图"
