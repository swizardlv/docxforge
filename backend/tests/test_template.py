"""Tests for DefaultTemplateEngine."""

from __future__ import annotations

from pathlib import Path

import pytest
from docxforge.config import Settings
from docxforge.core.officecli import DefaultOfficeCLIRunner
from docxforge.core.template import DefaultTemplateEngine
from docxforge.errors import TemplateNotFoundError


@pytest.mark.officecli
def test_template_register_list_delete(template_docx: Path, workdir: Path) -> None:
    settings = Settings(templates_dir=workdir / "templates")
    runner = DefaultOfficeCLIRunner(settings)
    engine = DefaultTemplateEngine(settings, runner)

    # Register
    info = engine.register_from_docx(template_docx, name="测试模板")
    assert info.template_id
    assert info.name == "测试模板"

    # List
    templates = engine.list_templates()
    assert len(templates) == 1
    assert templates[0].template_id == info.template_id

    # Get
    got = engine.get_template(info.template_id)
    assert got.name == "测试模板"

    # Delete
    engine.delete_template(info.template_id)
    assert len(engine.list_templates()) == 0

    with pytest.raises(TemplateNotFoundError):
        engine.get_template(info.template_id)


@pytest.mark.officecli
def test_template_prepare_base_without_template(workdir: Path) -> None:
    settings = Settings(templates_dir=workdir / "templates")
    engine = DefaultTemplateEngine(settings)

    dest = workdir / "blank_base.docx"
    prepared = engine.prepare_base(None, dest)

    assert prepared.path == dest
    assert dest.exists()
    assert prepared.template_id is None
    assert prepared.cover_paragraph_count == 0


@pytest.mark.officecli
def test_template_prepare_base_with_template(template_docx: Path, workdir: Path) -> None:
    settings = Settings(templates_dir=workdir / "templates")
    engine = DefaultTemplateEngine(settings)

    info = engine.register_from_docx(template_docx, name="基础模版")
    dest = workdir / "prepared.docx"

    prepared = engine.prepare_base(info.template_id, dest)

    assert prepared.path == dest
    assert dest.exists()
    assert prepared.template_id == info.template_id


@pytest.mark.officecli
def test_template_cover_detection(template_docx: Path, workdir: Path) -> None:
    """The leading run of body paragraphs is detected as the cover section."""
    settings = Settings(templates_dir=workdir / "templates")
    engine = DefaultTemplateEngine(settings)

    info = engine.register_from_docx(template_docx, name="带封皮模板")
    # The fixture template has one Title paragraph at the start of /body.
    assert info.has_cover is True
    assert info.cover_paragraph_count >= 1


@pytest.mark.officecli
def test_template_style_map_from_styles(template_docx: Path, workdir: Path) -> None:
    settings = Settings(templates_dir=workdir / "templates")
    engine = DefaultTemplateEngine(settings)

    info = engine.register_from_docx(template_docx, name="样式模板")
    style_map = engine.style_map_for(info.template_id)

    assert style_map.paragraph == "Normal"
    assert style_map.heading(1) == "Heading1"

    # Unknown template id falls back to the default map without raising.
    assert engine.style_map_for("missing_id").paragraph == "Normal"


# ---------------------------------------------------------------------------
# Style parsing / inference (pure functions, no officecli binary needed)
# ---------------------------------------------------------------------------


def _sample_style_dump() -> list[dict]:
    """A minimal /styles dump replay with fonts, sizes and colors."""
    return [
        {"command": "meta", "dumpVersion": 2},
        {
            "command": "add",
            "parent": "/styles",
            "type": "style",
            "props": {"id": "a", "type": "paragraph", "name": "Normal"},
        },
        {"command": "add", "parent": "/styles/a/rPr[1]", "type": "w:rFonts",
         "props": {"w:ascii": "Times New Roman", "w:eastAsia": "宋体"}},
        {"command": "add", "parent": "/styles/a/rPr[1]", "type": "w:sz",
         "props": {"w:val": "24"}},
        {"command": "add", "parent": "/styles/a/rPr[1]", "type": "w:color",
         "props": {"w:val": "FF0000"}},
        {"command": "add", "parent": "/styles/a", "type": "w:b", "props": {}},
        {
            "command": "add",
            "parent": "/styles",
            "type": "style",
            "props": {"id": "1", "type": "paragraph", "name": "heading 1"},
        },
        {"command": "add", "parent": "/styles/1/rPr[1]", "type": "w:sz",
         "props": {"w:val": "32"}},
        {
            "command": "add",
            "parent": "/styles",
            "type": "style",
            "props": {"id": "af3", "type": "table", "name": "Table Grid"},
        },
    ]


def test_parse_styles_extracts_format_properties() -> None:
    infos = DefaultTemplateEngine._parse_styles(_sample_style_dump())
    assert len(infos) == 3

    normal = next(s for s in infos if s.style_id == "a")
    assert normal.name == "Normal"
    assert normal.font == "Times New Roman"
    assert normal.size_pt == 12.0  # 24 half-points
    assert normal.color == "FF0000"
    assert normal.bold is True

    heading = next(s for s in infos if s.style_id == "1")
    assert heading.size_pt == 16.0


def test_infer_style_map_matches_roles() -> None:
    infos = DefaultTemplateEngine._parse_styles(_sample_style_dump())
    sm = DefaultTemplateEngine._infer_style_map(infos)

    assert sm.heading(1) == "1"
    assert sm.paragraph == "a"
    assert sm.table == "af3"


def test_infer_style_map_chinese_headings() -> None:
    dump = [
        {"command": "add", "parent": "/styles", "type": "style",
         "props": {"id": "H1", "type": "paragraph", "name": "标题 1"}},
        {"command": "add", "parent": "/styles", "type": "style",
         "props": {"id": "H2", "type": "paragraph", "name": "标题 2"}},
        {"command": "add", "parent": "/styles", "type": "style",
         "props": {"id": "B", "type": "paragraph", "name": "正文"}},
    ]
    infos = DefaultTemplateEngine._parse_styles(dump)
    sm = DefaultTemplateEngine._infer_style_map(infos)
    assert sm.heading(1) == "H1"
    assert sm.heading(2) == "H2"
    assert sm.paragraph == "B"


def test_save_style_map_validates_and_persists(workdir: Path) -> None:
    settings = Settings(templates_dir=workdir / "templates")
    engine = DefaultTemplateEngine(settings)

    # Register from a config written directly (no officecli needed for save)
    tid = "tpl_unit"
    tdir = settings.templates_dir / tid
    tdir.mkdir(parents=True)
    config = {
        "info": {
            "template_id": tid,
            "name": "unit",
            "styles": [
                {"style_id": "a", "name": "Normal"},
                {"style_id": "1", "name": "heading 1"},
            ],
        },
        "styles": [],
    }
    (tdir / "template_config.json").write_text(
        __import__("json").dumps(config, ensure_ascii=False), encoding="utf-8"
    )

    from docxforge.models import StyleMap

    sm = StyleMap()
    sm.headings[1] = "1"
    sm.paragraph = "a"
    engine.save_style_map(tid, sm)

    saved = engine.style_map_for(tid)
    assert saved.heading(1) == "1"
    assert saved.paragraph == "a"


def test_save_style_map_rejects_unknown_style(workdir: Path) -> None:
    from docxforge.errors import TemplateError
    from docxforge.models import StyleMap

    settings = Settings(templates_dir=workdir / "templates")
    engine = DefaultTemplateEngine(settings)

    tid = "tpl_unit2"
    tdir = settings.templates_dir / tid
    tdir.mkdir(parents=True)
    config = {
        "info": {"template_id": tid, "name": "unit", "styles": []},
        "styles": [],
    }
    (tdir / "template_config.json").write_text(
        __import__("json").dumps(config, ensure_ascii=False), encoding="utf-8"
    )

    sm = StyleMap()
    sm.paragraph = "definitely_not_a_style"
    with pytest.raises(TemplateError):
        engine.save_style_map(tid, sm)
