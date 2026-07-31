"""Job lifecycle bookkeeping (``JobStore`` protocol) and the TTL reaper.

State machine::

    pending -> running -> ready     -> destroyed
                       -> failed    -> destroyed

``ready`` and ``failed`` jobs carry an ``expires_at`` set to
``now + ttl_seconds``; once that passes the job is expired. A destroyed job is
kept as a short-lived tombstone (so the UI can still render the terminal state)
and is dropped entirely after another TTL window.

Lookup semantics required by :class:`docxforge.interfaces.JobStore`:

* unknown id                      -> ``JobNotFoundError`` (404)
* known, TTL elapsed, not reaped  -> ``JobExpiredError`` (410)
* destroyed tombstone             -> returned with ``state=destroyed``
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone

from docxforge.config import Settings, get_settings
from docxforge.errors import JobExpiredError, JobNotFoundError
from docxforge.interfaces import Sandbox
from docxforge.models import DestroyReport, JobInfo, JobState, RenderResult

logger = logging.getLogger(__name__)

__all__ = ["InMemoryJobStore", "JobReaper"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryJobStore:
    """Thread-safe, process-local job registry backed by a sandbox.

    Nothing is persisted: restarting the process forgets every job, which is
    exactly the privacy posture PRD module D asks for.
    """

    def __init__(
        self,
        sandbox: Sandbox,
        *,
        settings: Settings | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._sandbox = sandbox
        self.ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else self._settings.job_ttl_seconds
        )
        self._lock = threading.RLock()
        self._jobs: dict[str, JobInfo] = {}
        #: Render results are kept out of ``JobInfo`` because that model is a
        #: frozen wire contract and must not leak filesystem paths.
        self._results: dict[str, RenderResult] = {}

    # -- creation --------------------------------------------------------

    def create_job(self, *, ttl_seconds: int | None = None) -> JobInfo:
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        created = _now()
        job = JobInfo(
            job_id=uuid.uuid4().hex,
            state=JobState.PENDING,
            created_at=created,
            expires_at=created + timedelta(seconds=ttl),
            ttl_seconds=ttl,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    # -- lookup ----------------------------------------------------------

    def get_job(self, job_id: str) -> JobInfo:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError("任务不存在或已被销毁", detail=f"job_id={job_id}")
            if job.state is JobState.DESTROYED:
                return job.model_copy(deep=True)
            if self._is_expired(job):
                raise JobExpiredError(
                    "任务已过期，临时数据已被销毁", detail=f"job_id={job_id}"
                )
            return job.model_copy(deep=True)

    def peek_job(self, job_id: str) -> JobInfo | None:
        """Raw record lookup that never raises. For internal/route use."""
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job is not None else None

    def list_jobs(self) -> list[JobInfo]:
        with self._lock:
            return [job.model_copy(deep=True) for job in self._jobs.values()]

    def get_result(self, job_id: str) -> RenderResult:
        """The render result of a ready job (holds the on-disk output path)."""
        with self._lock:
            result = self._results.get(job_id)
        if result is None:
            raise JobNotFoundError("任务结果不存在", detail=f"job_id={job_id}")
        return result

    # -- transitions -----------------------------------------------------

    def mark_running(self, job_id: str) -> JobInfo:
        return self._update(job_id, state=JobState.RUNNING)

    def mark_ready(self, job_id: str, result: RenderResult) -> JobInfo:
        with self._lock:
            self._results[job_id] = result
        now = _now()
        job = self._update(
            job_id,
            state=JobState.READY,
            filename=result.filename,
            elapsed_ms=result.elapsed_ms,
            warnings=list(result.warnings),
            # The countdown the user sees starts when the file is ready.
            expires_at=now + timedelta(seconds=self._ttl_of(job_id)),
        )
        return job

    def mark_failed(self, job_id: str, error: str) -> JobInfo:
        return self._update(
            job_id,
            state=JobState.FAILED,
            error=error,
            expires_at=_now() + timedelta(seconds=self._ttl_of(job_id)),
        )

    # -- destruction -----------------------------------------------------

    def destroy_job(self, job_id: str) -> DestroyReport:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError("任务不存在或已被销毁", detail=f"job_id={job_id}")
        report = self._sandbox.destroy(job_id)
        self._update(
            job_id,
            state=JobState.DESTROYED,
            destroyed_at=report.destroyed_at or _now(),
        )
        with self._lock:
            self._results.pop(job_id, None)
        return report

    def destroy_expired(self) -> list[DestroyReport]:
        """Shred every job past its TTL and drop stale tombstones.

        Also sweeps sandbox directories that no longer have a job record
        (crash leftovers), so nothing survives the TTL window on disk.
        """
        now = _now()
        reports: list[DestroyReport] = []

        with self._lock:
            expired = [
                job.job_id
                for job in self._jobs.values()
                if job.state is not JobState.DESTROYED and self._is_expired(job, now=now)
            ]
            stale_tombstones = [
                job.job_id
                for job in self._jobs.values()
                if job.state is JobState.DESTROYED
                and job.destroyed_at is not None
                and (now - job.destroyed_at).total_seconds() >= job.ttl_seconds
            ]

        for job_id in expired:
            try:
                reports.append(self.destroy_job(job_id))
            except JobNotFoundError:  # pragma: no cover - lost a race, fine
                continue

        with self._lock:
            for job_id in stale_tombstones:
                self._jobs.pop(job_id, None)
                self._results.pop(job_id, None)

        reports.extend(self._sandbox.destroy_expired())
        return reports

    def destroy_all(self) -> list[DestroyReport]:
        """Shred everything. Used on application shutdown."""
        with self._lock:
            job_ids = [
                job.job_id
                for job in self._jobs.values()
                if job.state is not JobState.DESTROYED
            ]
        reports: list[DestroyReport] = []
        for job_id in job_ids:
            try:
                reports.append(self.destroy_job(job_id))
            except JobNotFoundError:  # pragma: no cover - lost a race, fine
                continue
        return reports

    # -- internals -------------------------------------------------------

    def _ttl_of(self, job_id: str) -> int:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.ttl_seconds if job is not None else self.ttl_seconds

    @staticmethod
    def _is_expired(job: JobInfo, *, now: datetime | None = None) -> bool:
        if job.expires_at is None:
            return False
        return (now or _now()) >= job.expires_at

    def _update(self, job_id: str, **changes: object) -> JobInfo:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError("任务不存在或已被销毁", detail=f"job_id={job_id}")
            updated = job.model_copy(update=changes)
            self._jobs[job_id] = updated
            return updated.model_copy(deep=True)


class JobReaper:
    """Background loop that calls ``destroy_expired`` on a fixed interval."""

    def __init__(
        self,
        store: InMemoryJobStore,
        *,
        interval_seconds: float | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        self._store = store
        self.interval_seconds = (
            interval_seconds
            if interval_seconds is not None
            else resolved.reaper_interval_seconds
        )
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="docxforge-job-reaper")

    async def stop(self) -> None:
        self._stopping.set()
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def sweep_once(self) -> list[DestroyReport]:
        return await asyncio.to_thread(self._store.destroy_expired)

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self.interval_seconds
                )
                return
            except asyncio.TimeoutError:  # noqa: UP041 - alias differs on 3.10
                pass
            try:
                await self.sweep_once()
            except Exception:  # pragma: no cover - the loop must never die
                logger.exception("job reaper sweep failed")
