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
