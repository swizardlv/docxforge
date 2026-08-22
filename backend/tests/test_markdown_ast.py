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


def test_parse_empty_markdown() -> None:
    parser = DefaultMarkdownParser()
    ast = parser.parse("")
    assert ast.nodes == []
    assert ast.doc_title is None


def test_parse_markdown_nested_list() -> None:
    parser = DefaultMarkdownParser()
    md = "- item1\n  - nested1\n  - nested2\n- item2\n  - nested3\n"
    ast = parser.parse(md)

    from docxforge.models import ListNode

    lists = [node for node in ast.nodes if isinstance(node, ListNode)]
    assert len(lists) == 1
    items = lists[0].items
    assert [(i.content, i.level) for i in items] == [
        ("item1", 0),
        ("nested1", 1),
        ("nested2", 1),
        ("item2", 0),
        ("nested3", 1),
    ]


def test_parse_markdown_table_headers_and_rows() -> None:
    parser = DefaultMarkdownParser()
    md = (
        "| 序号 | 模块 | 工期 |\n"
        "| --- | --- | --- |\n"
        "| 1 | 需求调研 | 5天 |\n"
        "| 2 | 系统开发 | 15天 |\n"
    )
    ast = parser.parse(md)

    tables = [node for node in ast.nodes if isinstance(node, TableNode)]
    assert len(tables) == 1
    assert tables[0].headers == ["序号", "模块", "工期"]
    assert tables[0].rows == [["1", "需求调研", "5天"], ["2", "系统开发", "15天"]]


def test_parse_markdown_quote_and_pagebreak() -> None:
    parser = DefaultMarkdownParser()

    from docxforge.models import PageBreakNode, QuoteNode

    md = "> 引用内容\n\n[pagebreak]\n"
    ast = parser.parse(md)
    assert any(isinstance(node, QuoteNode) for node in ast.nodes)
    assert any(isinstance(node, PageBreakNode) for node in ast.nodes)


def test_parse_markdown_image() -> None:
    parser = DefaultMarkdownParser()
    md = "# 架构图\n\n![系统架构示意图](https://example.com/arch.png)\n"
    ast = parser.parse(md)

    from docxforge.models import ImageNode

    images = [node for node in ast.nodes if isinstance(node, ImageNode)]
    assert len(images) == 1
    assert images[0].src == "https://example.com/arch.png"
    assert images[0].alt == "系统架构示意图"
