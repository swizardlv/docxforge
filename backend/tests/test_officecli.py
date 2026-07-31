"""Tests for DefaultOfficeCLIRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from docxforge.core.officecli import DefaultOfficeCLIRunner
from docxforge.errors import OfficeCLIError
from docxforge.models import BatchItem


@pytest.mark.officecli
def test_officecli_version(officecli_bin: str) -> None:
    runner = DefaultOfficeCLIRunner()
    version = runner.version()
    assert version
    assert "." in version


@pytest.mark.officecli
def test_officecli_create_and_get(workdir: Path) -> None:
    runner = DefaultOfficeCLIRunner()
    doc = workdir / "test_create.docx"
    runner.create(doc)
    assert doc.exists()

    data = runner.get(doc, "/")
    assert isinstance(data, dict)


@pytest.mark.officecli
def test_officecli_add_and_set(workdir: Path) -> None:
    runner = DefaultOfficeCLIRunner()
    doc = workdir / "test_add.docx"
    runner.create(doc)

    node_path = runner.add(
        doc, "/body", type="paragraph", props={"text": "Hello World", "style": "Heading1"}
    )
    assert node_path

    runner.set(doc, "/body/p[1]", props={"style": "Normal"})


@pytest.mark.officecli
def test_officecli_batch(workdir: Path) -> None:
    runner = DefaultOfficeCLIRunner()
    doc = workdir / "test_batch.docx"
    runner.create(doc)

    items = [
        BatchItem(
            command="add",
            parent="/body",
            type="paragraph",
            props={"text": "Batch Paragraph 1", "style": "Heading1"},
        ),
        BatchItem(
            command="add",
            parent="/body",
            type="paragraph",
            props={"text": "Batch Paragraph 2", "style": "Normal"},
        ),
    ]

    outcome = runner.batch(doc, items)
    assert outcome.total == 2
    assert outcome.executed >= 0
    assert outcome.failed == 0


@pytest.mark.officecli
def test_officecli_invalid_command(workdir: Path) -> None:
    runner = DefaultOfficeCLIRunner()
    doc = workdir / "nonexistent.docx"
    with pytest.raises(OfficeCLIError):
        runner.get(doc, "/invalid_path_xxx")
