"""Ephemeral per-job scratch space with physical destruction (PRD module D).

Implements the ``Sandbox`` protocol from :mod:`docxforge.interfaces`.

Every job owns one directory under ``settings.sandbox_root``. On Linux that
root lives on ``/dev/shm`` (RAM-backed); on macOS it falls back to the OS temp
dir, where the ephemeral guarantee is enforced by this module instead of by
the filesystem: every file is overwritten with random bytes ``shred_passes``
times, truncated, unlinked, and finally the directory itself is removed.

This module is the evidence source for DoD #3 (zero data remnants).
"""

from __future__ import annotations

import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from docxforge.config import Settings, get_settings
from docxforge.errors import JobNotFoundError
from docxforge.models import DestroyReport

__all__ = [
    "EphemeralSandbox",
    "JOB_ID_PATTERN",
    "overwrite_file",
    "shred_file",
    "validate_job_id",
]

#: Job ids are uuid4 (hex with optional dashes) or plain hex tokens. The
#: pattern is deliberately narrow: it makes ``..``, ``/``, ``\`` and absolute
#: paths unrepresentable, so a job id can never escape the sandbox root.
JOB_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{1,32}(?:-[0-9a-fA-F]{1,32}){0,4}$")

#: Overwrite buffer size; keeps memory flat for large documents.
_CHUNK_SIZE = 1 << 20


def validate_job_id(job_id: str) -> str:
    """Return ``job_id`` when it is a safe path segment, else raise.

    Raises:
        JobNotFoundError: the id is empty, malformed, or attempts traversal.
    """
    if not isinstance(job_id, str) or not JOB_ID_PATTERN.match(job_id):
        raise JobNotFoundError(
            "任务 ID 非法",
            detail=f"job_id must match {JOB_ID_PATTERN.pattern!r}",
        )
    return job_id


def overwrite_file(path: Path, passes: int = 1) -> int:
    """Overwrite ``path`` in place with random bytes.

    The file keeps its size and stays on disk; :func:`shred_file` is the
    variant that also unlinks. Symlinks are never followed.

    Returns:
        The number of bytes overwritten (0 for symlinks and empty files).
    """
    if path.is_symlink():
        return 0
    size = path.lstat().st_size
    if size == 0:
        return 0
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - best effort on exotic filesystems
        pass
    with open(path, "r+b", buffering=0) as handle:
        for _ in range(max(1, passes)):
            handle.seek(0)
            remaining = size
            while remaining > 0:
                chunk = min(_CHUNK_SIZE, remaining)
                handle.write(os.urandom(chunk))
                remaining -= chunk
            handle.flush()
            os.fsync(handle.fileno())
    return size


def shred_file(path: Path, passes: int = 1) -> int:
    """Overwrite, truncate and unlink ``path``.

    Returns:
        The original size in bytes (0 when the file was a symlink, empty or
        already gone).
    """
    if path.is_symlink():
        path.unlink(missing_ok=True)
        return 0
    if not path.exists():
        return 0
    size = overwrite_file(path, passes)
    try:
        with open(path, "r+b", buffering=0) as handle:
            handle.truncate(0)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:  # pragma: no cover - unlink below still removes the entry
        pass
    path.unlink(missing_ok=True)
    return size


class EphemeralSandbox:
    """Per-job scratch directories that are shredded on destruction."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        root: Path | None = None,
        ttl_seconds: int | None = None,
        shred_passes: int | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self.root = Path(root or self._settings.sandbox_root)
        self.ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else self._settings.job_ttl_seconds
        )
        self.shred_passes = (
            shred_passes if shred_passes is not None else self._settings.shred_passes
        )
        self._lock = threading.RLock()
        #: job_id -> monotonic-free wall clock of creation, used for TTL sweeps.
        #: Directories not in this map (e.g. leftovers from a previous process)
        #: fall back to their mtime.
        self._created_at: dict[str, float] = {}

    # -- layout ----------------------------------------------------------

    def ensure_root(self) -> Path:
        """Create the sandbox root with owner-only permissions."""
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:  # pragma: no cover - best effort
            pass
        return self.root

    def path_for(self, job_id: str) -> Path:
        validate_job_id(job_id)
        candidate = self.root / job_id
        # Defence in depth: the regex already forbids separators, but a
        # symlinked root or an exotic id must never widen the blast radius.
        resolved_root = self.root.resolve()
        if resolved_root not in candidate.resolve().parents:
            raise JobNotFoundError(
                "任务 ID 非法",
                detail="resolved sandbox path escapes the sandbox root",
            )
        return candidate

    def create(self, job_id: str) -> Path:
        path = self.path_for(job_id)
        self.ensure_root()
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except OSError:  # pragma: no cover - best effort
            pass
        with self._lock:
            self._created_at.setdefault(job_id, time.time())
        return path

    def exists(self, job_id: str) -> bool:
        return self.path_for(job_id).is_dir()

    # -- destruction -----------------------------------------------------

    def destroy(self, job_id: str) -> DestroyReport:
        """Shred every file of the job, then remove its directory.

        Idempotent: destroying an unknown or already-destroyed job reports
        ``destroyed=True`` with zero counters.
        """
        path = self.path_for(job_id)
        files_shredded = 0
        bytes_shredded = 0

        if path.is_dir():
            for dirpath, dirnames, filenames in os.walk(path, topdown=False):
                current = Path(dirpath)
                for name in filenames:
                    bytes_shredded += shred_file(current / name, self.shred_passes)
                    files_shredded += 1
                for name in dirnames:
                    nested = current / name
                    if nested.is_symlink():
                        nested.unlink(missing_ok=True)
                    else:
                        nested.rmdir()
            path.rmdir()
        elif path.exists() or path.is_symlink():  # pragma: no cover - defensive
            bytes_shredded += shred_file(path, self.shred_passes)
            files_shredded += 1

        with self._lock:
            self._created_at.pop(job_id, None)

        exists_after = path.exists() or path.is_symlink()
        return DestroyReport(
            job_id=job_id,
            destroyed=not exists_after,
            files_shredded=files_shredded,
            bytes_shredded=bytes_shredded,
            sandbox_path=path,
            sandbox_exists_after=exists_after,
            destroyed_at=datetime.now(timezone.utc),
        )

    def destroy_expired(self) -> list[DestroyReport]:
        """Shred every job directory older than the TTL."""
        reports: list[DestroyReport] = []
        for job_id in self._expired_job_ids():
            reports.append(self.destroy(job_id))
        return reports

    def list_jobs(self) -> list[str]:
        """Job ids that currently own a sandbox directory."""
        if not self.root.is_dir():
            return []
        found: list[str] = []
        for entry in self.root.iterdir():
            if entry.is_dir() and not entry.is_symlink() and JOB_ID_PATTERN.match(entry.name):
                found.append(entry.name)
        return sorted(found)

    def age_seconds(self, job_id: str) -> float:
        """Seconds since the job directory was created."""
        with self._lock:
            created = self._created_at.get(job_id)
        if created is None:
            path = self.root / job_id
            try:
                created = path.stat().st_mtime
            except OSError:
                return 0.0
        return max(0.0, time.time() - created)

    def _expired_job_ids(self) -> list[str]:
        return [
            job_id
            for job_id in self.list_jobs()
            if self.age_seconds(job_id) >= self.ttl_seconds
        ]
