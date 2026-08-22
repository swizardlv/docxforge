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
