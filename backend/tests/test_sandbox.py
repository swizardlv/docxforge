"""Tests for the ephemeral sandbox (PRD module D, DoD #3)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from docxforge.config import Settings
from docxforge.core.sandbox import (
    EphemeralSandbox,
    overwrite_file,
    shred_file,
    validate_job_id,
)
from docxforge.errors import JobNotFoundError

JOB_A = "0123456789abcdef0123456789abcdef"
JOB_B = "fedcba9876543210fedcba9876543210"
UUID_JOB = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        sandbox_root=tmp_path / "sandbox",
        job_ttl_seconds=60,
        shred_passes=2,
    )


@pytest.fixture
def sandbox(settings: Settings) -> EphemeralSandbox:
    return EphemeralSandbox(settings)


def _populate(directory: Path) -> dict[Path, bytes]:
    """Write a realistic job payload and return path -> content."""
    payload = {
        directory / "source.md": "# 投标文件\n\n机密正文内容。".encode(),
        directory / "output.docx": os.urandom(4096),
        directory / "nested" / "template.docx": os.urandom(1024),
    }
    for path, content in payload.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return payload


# -- layout -----------------------------------------------------------------


def test_create_makes_isolated_directory(sandbox: EphemeralSandbox) -> None:
    path_a = sandbox.create(JOB_A)
    path_b = sandbox.create(JOB_B)

    assert path_a.is_dir()
    assert path_b.is_dir()
    assert path_a != path_b
    assert path_a.parent == sandbox.root
    assert sandbox.exists(JOB_A)
    assert sandbox.path_for(JOB_A) == path_a
    assert oct(path_a.stat().st_mode)[-3:] == "700"


def test_exists_is_false_before_create(sandbox: EphemeralSandbox) -> None:
    assert sandbox.exists(JOB_A) is False


# -- shredding --------------------------------------------------------------


def test_overwrite_file_replaces_content_in_place(tmp_path: Path) -> None:
    target = tmp_path / "secret.md"
    original = b"absolutely-confidential-bid-content" * 16
    target.write_bytes(original)

    written = overwrite_file(target, passes=2)

    assert written == len(original)
    assert target.exists()
    after = target.read_bytes()
    assert len(after) == len(original)
    assert after != original
    assert b"confidential" not in after


def test_shred_file_removes_the_entry(tmp_path: Path) -> None:
    target = tmp_path / "out.docx"
    target.write_bytes(b"x" * 2048)

    size = shred_file(target, passes=1)

    assert size == 2048
    assert not target.exists()


def test_shred_file_is_idempotent(tmp_path: Path) -> None:
    assert shred_file(tmp_path / "missing.docx", passes=1) == 0


def test_destroy_reports_and_removes_everything(sandbox: EphemeralSandbox) -> None:
    directory = sandbox.create(JOB_A)
    payload = _populate(directory)
    expected_bytes = sum(len(content) for content in payload.values())

    report = sandbox.destroy(JOB_A)

    assert report.job_id == JOB_A
    assert report.destroyed is True
    assert report.files_shredded == len(payload)
    assert report.bytes_shredded == expected_bytes
    assert report.sandbox_path == directory
    assert report.sandbox_exists_after is False
    assert report.destroyed_at is not None

    assert not directory.exists()
    for path in payload:
        assert not path.exists()
    assert sandbox.exists(JOB_A) is False


def test_destroy_leaves_no_docx_or_md_behind(sandbox: EphemeralSandbox) -> None:
    """DoD #3: no ``*.docx`` / ``*.md`` remains anywhere under the root."""
    directory = sandbox.create(JOB_A)
    _populate(directory)
    other = sandbox.create(JOB_B)
    (other / "keep.docx").write_bytes(b"another job")

    sandbox.destroy(JOB_A)

    assert list(sandbox.root.rglob("*.md")) == []
    remaining = list(sandbox.root.rglob("*.docx"))
    assert remaining == [other / "keep.docx"]

    sandbox.destroy(JOB_B)
    assert list(sandbox.root.rglob("*.docx")) == []
    assert list(sandbox.root.rglob("*")) == []


def test_destroy_is_idempotent(sandbox: EphemeralSandbox) -> None:
    sandbox.create(JOB_A)
    sandbox.destroy(JOB_A)

    report = sandbox.destroy(JOB_A)

    assert report.destroyed is True
    assert report.files_shredded == 0
    assert report.bytes_shredded == 0
    assert report.sandbox_exists_after is False


def test_destroy_unknown_job_does_not_raise(sandbox: EphemeralSandbox) -> None:
    report = sandbox.destroy(JOB_B)
    assert report.destroyed is True


def test_destroy_handles_readonly_files(sandbox: EphemeralSandbox) -> None:
    directory = sandbox.create(JOB_A)
    locked = directory / "locked.docx"
    locked.write_bytes(b"read-only payload")
    os.chmod(locked, 0o400)

    report = sandbox.destroy(JOB_A)

    assert report.files_shredded == 1
    assert not locked.exists()


# -- TTL sweep --------------------------------------------------------------


def test_destroy_expired_only_sweeps_old_jobs(settings: Settings) -> None:
    settings = settings.model_copy(update={"job_ttl_seconds": 30})
    sandbox = EphemeralSandbox(settings)
    old_dir = sandbox.create(JOB_A)
    (old_dir / "old.docx").write_bytes(b"stale")
    fresh_dir = sandbox.create(JOB_B)
    (fresh_dir / "fresh.docx").write_bytes(b"recent")

    # Backdate the old job past its TTL.
    sandbox._created_at[JOB_A] -= 31

    reports = sandbox.destroy_expired()

    assert [report.job_id for report in reports] == [JOB_A]
    assert not old_dir.exists()
    assert fresh_dir.is_dir()
    assert sandbox.list_jobs() == [JOB_B]


def test_destroy_expired_uses_mtime_for_unknown_directories(settings: Settings) -> None:
    """Leftovers from a previous process still get swept."""
    sandbox = EphemeralSandbox(settings, ttl_seconds=10)
    sandbox.ensure_root()
    orphan = sandbox.root / UUID_JOB
    orphan.mkdir(parents=True)
    (orphan / "leftover.md").write_bytes(b"crash remnant")
    stale = orphan.stat().st_mtime - 3600
    os.utime(orphan, (stale, stale))

    reports = sandbox.destroy_expired()

    assert [report.job_id for report in reports] == [UUID_JOB]
    assert not orphan.exists()


def test_destroy_expired_returns_empty_when_root_missing(sandbox: EphemeralSandbox) -> None:
    assert sandbox.destroy_expired() == []
    assert sandbox.list_jobs() == []


# -- traversal defence ------------------------------------------------------


@pytest.mark.parametrize(
    "job_id",
    [
        "",
        "..",
        "../evil",
        "../../etc/passwd",
        "/etc/passwd",
        "a/b",
        "job..id",
        "zzzz",  # not hex
        "job_id",
        ".",
        "0123456789abcdef0123456789abcdef0",  # too long for one segment
    ],
)
def test_invalid_job_ids_are_rejected(sandbox: EphemeralSandbox, job_id: str) -> None:
    with pytest.raises(JobNotFoundError):
        validate_job_id(job_id)
    with pytest.raises(JobNotFoundError):
        sandbox.path_for(job_id)
    with pytest.raises(JobNotFoundError):
        sandbox.create(job_id)
    with pytest.raises(JobNotFoundError):
        sandbox.destroy(job_id)


def test_traversal_cannot_touch_files_outside_the_root(sandbox: EphemeralSandbox) -> None:
    outside = sandbox.root.parent / "victim.docx"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_bytes(b"must survive")

    with pytest.raises(JobNotFoundError):
        sandbox.destroy("../victim.docx")

    assert outside.read_bytes() == b"must survive"


def test_uuid_job_ids_are_accepted(sandbox: EphemeralSandbox) -> None:
    assert validate_job_id(UUID_JOB) == UUID_JOB
    assert sandbox.create(UUID_JOB).name == UUID_JOB
