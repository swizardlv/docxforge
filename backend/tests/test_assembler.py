"""Tests for DefaultDocumentAssembler."""

from __future__ import annotations

from pathlib import Path

from docxforge.core.assembler import DefaultDocumentAssembler
from docxforge.models import CoverOptions, PreparedBase, TocOptions


def test_assembler_toc_commands(tmp_path: Path) -> None:
    assembler = DefaultDocumentAssembler()
    base = PreparedBase(path=tmp_path / "doc.docx")
    toc_opts = TocOptions(enabled=True, levels="1-3")

    items = assembler.toc_commands(toc_opts, base)
    assert len(items) == 1
    assert items[0].type == "toc"
    assert items[0].props["levels"] == "1-3"


def test_assembler_cover_commands(tmp_path: Path) -> None:
    assembler = DefaultDocumentAssembler()
    base = PreparedBase(path=tmp_path / "doc.docx")
    cover_opts = CoverOptions(enabled=True, replacements={"原标题": "测试标书标题"})

    items = assembler.cover_commands(cover_opts, base)
    assert len(items) == 1
    assert items[0].props["find"] == "原标题"
    assert items[0].props["replace"] == "测试标书标题"
