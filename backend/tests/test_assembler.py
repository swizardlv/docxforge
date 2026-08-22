"""Tests for DefaultDocumentAssembler."""

from __future__ import annotations

from pathlib import Path

from docxforge.core.assembler import DefaultDocumentAssembler
from docxforge.models import CoverOptions, PreparedBase, TocOptions


def test_assembler_toc_commands(tmp_path: Path) -> None:
    assembler = DefaultDocumentAssembler()
    base = PreparedBase(path=tmp_path / "doc.docx")
    toc_opts = TocOptions(enabled=True, levels="1-3")

    # TOC add + trailing page break (page_break_after defaults to True).
    items = assembler.toc_commands(toc_opts, base)
    assert len(items) == 2
    assert items[0].type == "toc"
    assert items[0].props["levels"] == "1-3"
    assert items[1].type == "pagebreak"
    assert items[1].props["type"] == "page"

    # Disabling the trailing page break yields just the TOC.
    toc_no_break = TocOptions(enabled=True, levels="1-3", page_break_after=False)
    items = assembler.toc_commands(toc_no_break, base)
    assert len(items) == 1
    assert items[0].type == "toc"


def test_assembler_cover_commands(tmp_path: Path) -> None:
    assembler = DefaultDocumentAssembler()
    base = PreparedBase(path=tmp_path / "doc.docx")
    cover_opts = CoverOptions(enabled=True, replacements={"原标题": "测试标书标题"})

    items = assembler.cover_commands(cover_opts, base)
    assert len(items) == 1
    assert items[0].props["find"] == "原标题"
    assert items[0].props["replace"] == "测试标书标题"


def test_assembler_cover_commands_page_break_after_cover(tmp_path: Path) -> None:
    assembler = DefaultDocumentAssembler()
    base = PreparedBase(path=tmp_path / "doc.docx", cover_paragraph_count=3)
    cover_opts = CoverOptions(enabled=True, replacements={"原标题": "新标题"})

    items = assembler.cover_commands(cover_opts, base)
    assert len(items) == 2
    assert items[1].command == "add"
    assert items[1].type == "pagebreak"


def test_assembler_header_footer_creates_parts(tmp_path: Path) -> None:
    from docxforge.models import HeaderFooterOptions

    assembler = DefaultDocumentAssembler()
    base = PreparedBase(path=tmp_path / "doc.docx")
    opts = HeaderFooterOptions(header_text="页眉", footer_text="页脚")

    items = assembler.header_footer_commands(opts, base)
    assert len(items) == 4
    # header part + paragraph
    assert items[0].command == "add"
    assert items[0].type == "header"
    assert items[1].parent == "/header[1]"
    assert items[1].props["text"] == "页眉"
    # footer part + paragraph
    assert items[2].command == "add"
    assert items[2].type == "footer"
    assert items[3].parent == "/footer[1]"
    assert items[3].props["text"] == "页脚"
