"""FastAPI application factory.

Wiring lives here: the sandbox, the job store and the TTL reaper are created
once per application in the lifespan and exposed through ``app.state`` so the
providers in :mod:`docxforge.api.deps` (and test overrides) can reach them.

Run locally with::

    uv run uvicorn docxforge.api.main:app --port 8000 --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from docxforge import __version__
from docxforge.api.jobs import InMemoryJobStore, JobReaper
from docxforge.api.routes import router
from docxforge.config import Settings, get_settings
from docxforge.core.sandbox import EphemeralSandbox
from docxforge.errors import DocXForgeError
from docxforge.models import ErrorResponse

logger = logging.getLogger(__name__)

#: The Vite dev server. Production builds are served from the Tauri shell and
#: talk to 127.0.0.1 directly.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

DEV_PORT = 8000

__all__ = ["ALLOWED_ORIGINS", "DEV_PORT", "app", "create_app"]


def _error_response(status_code: int, payload: ErrorResponse) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        sandbox: EphemeralSandbox = app.state.sandbox
        sandbox.ensure_root()
        reaper: JobReaper = app.state.reaper
        await reaper.start()
        try:
            yield
        finally:
            await reaper.stop()
            # Privacy first: nothing outlives the process.
            store: InMemoryJobStore = app.state.job_store
            try:
                store.destroy_all()
            except Exception:  # pragma: no cover - shutdown must not raise
                logger.exception("failed to shred sandboxes on shutdown")

    app = FastAPI(
        title="DocXForge API",
        version=__version__,
        description="Markdown -> Pro-Word 标书渲染服务（本地优先，内存沙箱，TTL 物理销毁）",
        lifespan=lifespan,
    )

    sandbox = EphemeralSandbox(resolved)
    job_store = InMemoryJobStore(sandbox, settings=resolved)
    app.state.settings = resolved
    app.state.sandbox = sandbox
    app.state.job_store = job_store
    app.state.reaper = JobReaper(job_store, settings=resolved)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # The frontend needs the filename from the download response.
        expose_headers=["Content-Disposition", "Content-Length"],
    )

    @app.exception_handler(DocXForgeError)
    async def _docxforge_error_handler(_request, exc: DocXForgeError) -> JSONResponse:
        if exc.http_status >= 500:
            logger.error("%s: %s", exc.code, exc.message, exc_info=exc)
        return _error_response(
            exc.http_status,
            ErrorResponse(code=exc.code, message=exc.message, detail=exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(_request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            422,
            ErrorResponse(
                code="validation_error",
                message="请求参数不合法",
                detail=str(exc.errors()),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(_request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(
            exc.status_code,
            ErrorResponse(
                code="http_error",
                message=str(exc.detail),
                detail=None,
            ),
        )

    app.include_router(router)
    return app


app = create_app()


def main() -> None:  # pragma: no cover - manual entry point
    import uvicorn

    uvicorn.run("docxforge.api.main:app", host="127.0.0.1", port=DEV_PORT, reload=True)


if __name__ == "__main__":  # pragma: no cover
    main()
