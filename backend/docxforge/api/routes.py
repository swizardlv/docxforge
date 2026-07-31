"""HTTP endpoints.

The wire contract is docs/CONTRACTS.md section 3; field names here are frozen
and shared with the frontend. Every failure path raises a
:class:`docxforge.errors.DocXForgeError` subclass, which the application-level
handler renders as an ``ErrorResponse`` with ``exc.http_status``.
"""

from __future__ import annotations

import logging
import subprocess
import uuid
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from docxforge import __version__
from docxforge.api.deps import (
    get_job_store,
    get_officecli_runner,
    get_render_pipeline,
    get_sandbox,
    get_settings_dep,
    get_template_engine,
)
from docxforge.api.jobs import InMemoryJobStore
from docxforge.config import Settings
from docxforge.core.sandbox import shred_file
from docxforge.errors import (
    DocXForgeError,
    JobExpiredError,
    RenderError,
    TemplateError,
)
from docxforge.interfaces import OfficeCLIRunner, RenderPipeline, Sandbox, TemplateEngine
from docxforge.models import (
    DestroyReport,
    HealthResponse,
    JobInfo,
    JobState,
    RenderRequest,
    RenderResponse,
    TemplateInfo,
    TemplateListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED_TEMPLATE_SUFFIXES = (".docx", ".dotx")
_UPLOAD_CHUNK = 1 << 20

SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SandboxDep = Annotated[Sandbox, Depends(get_sandbox)]
# The concrete store lives in this package (it satisfies the JobStore
# protocol); routes also use its result bookkeeping, which is API-layer only.
JobStoreDep = Annotated[InMemoryJobStore, Depends(get_job_store)]
TemplateEngineDep = Annotated[TemplateEngine, Depends(get_template_engine)]
PipelineDep = Annotated[RenderPipeline, Depends(get_render_pipeline)]
RunnerDep = Annotated["OfficeCLIRunner | None", Depends(get_officecli_runner)]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def _probe_officecli(settings: Settings, runner: OfficeCLIRunner | None) -> tuple[bool, str | None]:
    """Best-effort availability + version probe. Never raises."""
    if runner is not None:
        try:
            if runner.is_available():
                return True, runner.version()
            return False, None
        except Exception:  # pragma: no cover - falls through to the CLI probe
            logger.debug("officecli runner probe failed, falling back", exc_info=True)
    binary = settings.resolve_officecli()
    if not binary:
        return False, None
    try:
        completed = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return False, None
    if completed.returncode != 0:
        return False, None
    return True, (completed.stdout or "").strip() or None


@router.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDep, runner: RunnerDep) -> HealthResponse:
    available, version = await run_in_threadpool(_probe_officecli, settings, runner)
    root = Path(settings.sandbox_root)
    return HealthResponse(
        status="ok" if available else "degraded",
        version=__version__,
        officecli_available=available,
        officecli_version=version,
        officecli_path=settings.resolve_officecli(),
        sandbox_root=root,
        sandbox_is_memory_backed=str(root).startswith("/dev/shm"),
        job_ttl_seconds=settings.job_ttl_seconds,
    )


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(engine: TemplateEngineDep) -> TemplateListResponse:
    templates = await run_in_threadpool(engine.list_templates)
    return TemplateListResponse(templates=list(templates))


@router.post("/templates", response_model=TemplateInfo)
async def upload_template(
    engine: TemplateEngineDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File(description="参考 .docx 模板")],
    name: Annotated[str | None, Form()] = None,
) -> TemplateInfo:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_TEMPLATE_SUFFIXES:
        raise TemplateError(
            "仅支持上传 .docx 或 .dotx 模板文件",
            detail=f"received filename={file.filename!r}",
        )

    staging_dir = Path(settings.sandbox_root) / "uploads"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged = staging_dir / f"{uuid.uuid4().hex}{suffix}"
    limit = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with open(staged, "wb") as sink:
            while True:
                chunk = await file.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise TemplateError(
                        f"模板文件过大，上限 {settings.max_upload_mb} MB",
                        detail=f"upload exceeded {limit} bytes",
                    )
                sink.write(chunk)
        if written == 0:
            raise TemplateError("上传的模板文件为空", detail="empty upload")
        return await run_in_threadpool(
            engine.register_from_docx, staged, name=name or Path(file.filename or "").stem
        )
    finally:
        # The upload is user data: shred the staging copy either way.
        shred_file(staged, settings.shred_passes)
        await file.close()


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(template_id: str, engine: TemplateEngineDep) -> Response:
    await run_in_threadpool(engine.delete_template, template_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Render / jobs
# ---------------------------------------------------------------------------


@router.post("/render", response_model=RenderResponse)
async def render(
    request: RenderRequest,
    pipeline: PipelineDep,
    store: JobStoreDep,
    sandbox: SandboxDep,
) -> RenderResponse:
    job = store.create_job()
    workdir = sandbox.create(job.job_id)
    store.mark_running(job.job_id)

    try:
        result = await run_in_threadpool(
            pipeline.render, request, workdir=workdir, job_id=job.job_id
        )
    except DocXForgeError as exc:
        store.mark_failed(job.job_id, exc.message)
        sandbox.destroy(job.job_id)
        raise
    except Exception as exc:  # normalize anything else into the shared hierarchy
        store.mark_failed(job.job_id, str(exc))
        sandbox.destroy(job.job_id)
        raise RenderError("文档渲染失败", detail=str(exc)) from exc

    ready = store.mark_ready(job.job_id, result)
    return RenderResponse(
        job_id=ready.job_id,
        filename=result.filename,
        download_url=f"/api/jobs/{ready.job_id}/download",
        elapsed_ms=result.elapsed_ms,
        expires_at=ready.expires_at,
        ttl_seconds=ready.ttl_seconds,
        warnings=list(result.warnings),
    )


@router.get("/jobs/{job_id}", response_model=JobInfo)
async def get_job(job_id: str, store: JobStoreDep) -> JobInfo:
    return store.get_job(job_id)


@router.get("/jobs/{job_id}/download")
async def download(
    job_id: str,
    store: JobStoreDep,
    settings: SettingsDep,
    runner: RunnerDep,
) -> Response:
    job = store.get_job(job_id)
    if job.state is JobState.DESTROYED:
        raise JobExpiredError("任务已销毁，文件不可再下载", detail=f"job_id={job_id}")
    if job.state is JobState.FAILED:
        raise RenderError("任务渲染失败，无文件可下载", detail=job.error)
    if job.state is not JobState.READY:
        raise RenderError("任务尚未完成，请稍后重试", detail=f"state={job.state.value}")

    result = store.get_result(job_id)
    path = Path(result.output_path)
    # CONTRACTS.md section 4: a resident officecli session may still hold the
    # document in memory; flush it before any non-officecli read.
    if runner is not None and not settings.no_auto_resident:
        try:
            await run_in_threadpool(runner.close, path)
        except Exception:  # pragma: no cover - a stale close must not 500
            logger.debug("officecli close before download failed", exc_info=True)

    if not path.is_file():
        raise JobExpiredError(
            "文件已被销毁或不存在", detail=f"missing output at {path}"
        )
    payload = await run_in_threadpool(path.read_bytes)
    return Response(
        content=payload,
        media_type=DOCX_MEDIA_TYPE,
        headers={
            "Content-Disposition": _content_disposition(result.filename),
            "Content-Length": str(len(payload)),
            "Cache-Control": "no-store",
        },
    )


@router.delete("/jobs/{job_id}", response_model=DestroyReport)
async def destroy_job(job_id: str, store: JobStoreDep) -> DestroyReport:
    return store.destroy_job(job_id)


def _content_disposition(filename: str | None) -> str:
    """RFC 6266 header with an ASCII fallback for Chinese filenames."""
    name = filename or "document.docx"
    suffix = Path(name).suffix.encode("ascii", "ignore").decode("ascii") or ".docx"
    stem = Path(name).stem.encode("ascii", "ignore").decode("ascii").strip().replace('"', "")
    fallback = f"{stem or 'document'}{suffix}"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name)}"


__all__ = ["DOCX_MEDIA_TYPE", "router"]
