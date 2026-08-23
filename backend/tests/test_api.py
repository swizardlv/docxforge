"""HTTP layer tests (docs/CONTRACTS.md section 3) plus job-store behaviour.

Sibling modules are developed in parallel, so the template engine, render
pipeline and officecli runner are injected as fakes through FastAPI dependency
overrides; nothing here imports a concrete implementation from ``core``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from docxforge.api.deps import (
    get_officecli_runner,
    get_render_pipeline,
    get_template_engine,
)
from docxforge.api.jobs import InMemoryJobStore, JobReaper
from docxforge.api.main import create_app
from docxforge.api.routes import DOCX_MEDIA_TYPE
from docxforge.config import Settings
from docxforge.core.sandbox import EphemeralSandbox
from docxforge.errors import JobExpiredError, JobNotFoundError, RenderError, TemplateError
from docxforge.models import (
    JobState,
    RenderRequest,
    RenderResult,
    TemplateInfo,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

DOCX_BYTES = b"PK\x03\x04fake-docx-payload" + bytes(512)
OUTPUT_FILENAME = "投标文件.docx"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakePipeline:
    """Stands in for ``core/pipeline.py`` (RenderPipeline protocol)."""

    def __init__(self) -> None:
        self.calls: list[tuple[RenderRequest, Path, str]] = []
        self.error: Exception | None = None

    def render(self, request: RenderRequest, *, workdir: Path, job_id: str) -> RenderResult:
        self.calls.append((request, workdir, job_id))
        if self.error is not None:
            raise self.error
        # Mirror what the real pipeline leaves behind: the markdown source and
        # the rendered document, both inside the job sandbox.
        (workdir / "source.md").write_text(request.markdown, encoding="utf-8")
        filename = f"{request.filename}.docx" if request.filename else OUTPUT_FILENAME
        output = workdir / filename
        output.write_bytes(DOCX_BYTES)
        return RenderResult(
            job_id=job_id,
            filename=filename,
            output_path=output,
            elapsed_ms=123,
            command_count=7,
            node_count=3,
            warnings=["fast_markdown 未启用"],
        )


class FakeTemplateEngine:
    """Stands in for ``core/template.py`` (TemplateEngine protocol)."""

    def __init__(self) -> None:
        self.templates: dict[str, TemplateInfo] = {}
        self.registered: list[tuple[Path, str | None, bytes]] = []
        self.deleted: list[str] = []

    def register_from_docx(
        self, source: Path, *, name: str | None = None, template_id: str | None = None
    ) -> TemplateInfo:
        # The staging file must still be readable while we are called.
        self.registered.append((source, name, source.read_bytes()))
        info = TemplateInfo(
            template_id=template_id or f"tpl_{len(self.templates) + 1}",
            name=name or source.stem,
            has_numbering=True,
            has_theme=True,
        )
        self.templates[info.template_id] = info
        return info

    def list_templates(self) -> list[TemplateInfo]:
        return list(self.templates.values())

    def get_template(self, template_id: str) -> TemplateInfo:
        if template_id not in self.templates:
            from docxforge.errors import TemplateNotFoundError

            raise TemplateNotFoundError(f"Template '{template_id}' not found")
        return self.templates[template_id]

    def delete_template(self, template_id: str) -> None:
        self.deleted.append(template_id)
        self.templates.pop(template_id, None)

    def styles_for(self, template_id: str) -> dict:
        info = self.get_template(template_id)
        return {
            "styles": [
                {
                    "style_id": s.style_id,
                    "name": s.name,
                    "type": s.type,
                    "font": s.font,
                    "size_pt": s.size_pt,
                    "color": s.color,
                    "bold": s.bold,
                    "italic": s.italic,
                    "line_spacing": s.line_spacing,
                    "alignment": s.alignment,
                    "role": "unused",
                }
                for s in info.styles
            ],
            "style_map": info.style_map.model_dump(mode="json"),
        }

    def save_style_map(self, template_id: str, style_map: object) -> None:
        info = self.get_template(template_id)
        from docxforge.models import StyleMap as StyleMapModel

        validated = StyleMapModel.model_validate(style_map)
        info.style_map = validated

    def save_cover_overrides(self, template_id: str, overrides: object) -> None:
        info = self.get_template(template_id)
        from docxforge.models import CoverOverride

        info.cover_overrides = [CoverOverride.model_validate(o) for o in overrides]

    def cover_overrides(self, template_id: str) -> list:
        return list(self.get_template(template_id).cover_overrides)

    def preview_for(self, template_id: str) -> dict:
        self.get_template(template_id)  # raises for unknown templates
        return {
            "cover": [
                {"type": "paragraph", "text": "封面标题", "style": "Title"},
                {"type": "table", "rows": [["项目名称", "示例项目"]]},
            ],
            "headings": [
                {"level": 1, "name": "heading 1", "font": "黑体", "size_pt": 22.0},
                {"level": 2, "name": "heading 2", "font": "黑体", "size_pt": 16.0},
                {"level": 3, "name": "heading 3"},
                {"level": 4, "name": "heading 4"},
                {"level": 5, "name": "heading 5"},
                {"level": 6, "name": "heading 6"},
            ],
            "header_text": "示例页眉",
            "footer_text": None,
        }


class FakeRunner:
    """Minimal officecli stand-in: version probe + flush-before-read."""

    def __init__(self, *, available: bool = True, version: str = "1.0.143") -> None:
        self._available = available
        self._version = version
        self.closed: list[Path] = []

    def is_available(self) -> bool:
        return self._available

    def version(self) -> str:
        return self._version

    def close(self, doc: Path) -> None:
        self.closed.append(Path(doc))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    base: dict[str, object] = {
        "sandbox_root": tmp_path / "sandbox",
        "templates_dir": tmp_path / "templates",
        "job_ttl_seconds": 60,
        "shred_passes": 1,
        "reaper_interval_seconds": 0.05,
        "max_upload_mb": 1,
    }
    base.update(overrides)
    return Settings(**base)


def build_app(
    settings: Settings,
    *,
    engine: FakeTemplateEngine,
    pipeline: FakePipeline,
    runner: FakeRunner | None,
) -> FastAPI:
    app = create_app(settings)
    app.dependency_overrides[get_template_engine] = lambda: engine
    app.dependency_overrides[get_render_pipeline] = lambda: pipeline
    app.dependency_overrides[get_officecli_runner] = lambda: runner
    return app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def engine() -> FakeTemplateEngine:
    return FakeTemplateEngine()


@pytest.fixture
def pipeline() -> FakePipeline:
    return FakePipeline()


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def app(
    settings: Settings,
    engine: FakeTemplateEngine,
    pipeline: FakePipeline,
    runner: FakeRunner,
) -> FastAPI:
    return build_app(settings, engine=engine, pipeline=pipeline, runner=runner)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def render_once(client: TestClient, **overrides: object) -> dict:
    body: dict[str, object] = {"markdown": "# 一、项目背景\n\n正文内容。"}
    body.update(overrides)
    response = client.post("/api/render", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_reports_sandbox_and_ttl(client: TestClient, settings: Settings) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["officecli_available"] is True
    assert payload["officecli_version"] == "1.0.143"
    assert Path(payload["sandbox_root"]) == settings.sandbox_root
    assert payload["job_ttl_seconds"] == 60
    assert payload["sandbox_is_memory_backed"] is False


def test_health_is_degraded_without_officecli(
    settings: Settings, engine: FakeTemplateEngine, pipeline: FakePipeline
) -> None:
    unavailable = FakeRunner(available=False)
    with TestClient(
        build_app(settings, engine=engine, pipeline=pipeline, runner=unavailable)
    ) as client:
        payload = client.get("/api/health").json()

    assert payload["status"] == "degraded"
    assert payload["officecli_available"] is False
    assert payload["officecli_version"] is None


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def test_list_templates_starts_empty(client: TestClient) -> None:
    response = client.get("/api/templates")

    assert response.status_code == 200
    assert response.json() == {"templates": []}


def test_upload_template_registers_and_shreds_the_staging_copy(
    client: TestClient, engine: FakeTemplateEngine, settings: Settings
) -> None:
    response = client.post(
        "/api/templates",
        files={"file": ("国标模板.docx", DOCX_BYTES, DOCX_MEDIA_TYPE)},
        data={"name": "国标模板"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["name"] == "国标模板"
    assert payload["template_id"]

    staged_path, name, content = engine.registered[0]
    assert name == "国标模板"
    assert content == DOCX_BYTES
    # The staging copy is user data and must not survive the request.
    assert not staged_path.exists()
    assert list((settings.sandbox_root / "uploads").iterdir()) == []

    listed = client.get("/api/templates").json()["templates"]
    assert [item["template_id"] for item in listed] == [payload["template_id"]]


def test_upload_template_rejects_other_extensions(client: TestClient) -> None:
    response = client.post(
        "/api/templates",
        files={"file": ("notes.md", b"# not a template", "text/markdown")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "template_error"


def test_upload_template_rejects_oversized_files(
    client: TestClient, settings: Settings, engine: FakeTemplateEngine
) -> None:
    oversized = bytes(settings.max_upload_mb * 1024 * 1024 + 1)

    response = client.post(
        "/api/templates",
        files={"file": ("huge.docx", oversized, DOCX_MEDIA_TYPE)},
    )

    assert response.status_code == 400
    assert "上限" in response.json()["message"]
    assert engine.registered == []
    assert list((settings.sandbox_root / "uploads").iterdir()) == []


def test_delete_template(client: TestClient, engine: FakeTemplateEngine) -> None:
    template_id = client.post(
        "/api/templates",
        files={"file": ("t.docx", DOCX_BYTES, DOCX_MEDIA_TYPE)},
    ).json()["template_id"]

    response = client.delete(f"/api/templates/{template_id}")

    assert response.status_code == 204
    assert engine.deleted == [template_id]


def test_get_template_styles(client: TestClient, engine: FakeTemplateEngine) -> None:
    from docxforge.models import StyleInfo

    template_id = client.post(
        "/api/templates",
        files={"file": ("t.docx", DOCX_BYTES, DOCX_MEDIA_TYPE)},
    ).json()["template_id"]
    info = engine.templates[template_id]
    info.styles = [
        StyleInfo(style_id="1", name="heading 1", type="paragraph", size_pt=16.0),
        StyleInfo(style_id="a", name="Normal", type="paragraph", size_pt=12.0),
    ]

    response = client.get(f"/api/templates/{template_id}/styles")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["styles"]) == 2
    assert payload["styles"][0]["style_id"] == "1"
    assert payload["styles"][0]["name"] == "heading 1"
    assert payload["styles"][0]["size_pt"] == 16.0
    assert "style_map" in payload


def test_put_style_map(client: TestClient, engine: FakeTemplateEngine) -> None:
    template_id = client.post(
        "/api/templates",
        files={"file": ("t.docx", DOCX_BYTES, DOCX_MEDIA_TYPE)},
    ).json()["template_id"]

    payload = {
        "headings": {"1": "1", "2": "Heading2", "3": "Heading3",
                     "4": "Heading4", "5": "Heading5", "6": "Heading6"},
        "paragraph": "a",
        "list_ordered": "ListNumber",
        "list_bullet": "ListBullet",
        "quote": "Quote",
        "code": "HTMLPreformatted",
        "caption": "Caption",
        "table": "TableGrid",
        "title": "Title",
    }
    response = client.put(
        f"/api/templates/{template_id}/style-map",
        json=payload,
    )
    assert response.status_code == 204
    assert engine.templates[template_id].style_map.heading(1) == "1"


def test_put_style_map_unknown_template(client: TestClient) -> None:
    payload = {
        "headings": {"1": "1", "2": "2", "3": "3",
                     "4": "4", "5": "5", "6": "6"},
        "paragraph": "a",
        "list_ordered": "b",
        "list_bullet": "c",
        "quote": "d",
        "code": "e",
        "caption": "f",
        "table": "g",
        "title": "h",
    }
    response = client.put("/api/templates/nope/style-map", json=payload)
    assert response.status_code == 404


def test_get_template_preview(client: TestClient, engine: FakeTemplateEngine) -> None:
    template_id = client.post(
        "/api/templates",
        files={"file": ("t.docx", DOCX_BYTES, DOCX_MEDIA_TYPE)},
    ).json()["template_id"]

    response = client.get(f"/api/templates/{template_id}/preview")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["cover"]) >= 1
    assert payload["cover"][0]["type"] == "paragraph"
    assert len(payload["headings"]) == 6
    assert payload["headings"][0]["level"] == 1


def test_get_template_preview_unknown(client: TestClient) -> None:
    response = client.get("/api/templates/nope/preview")
    assert response.status_code == 404


def test_put_cover_overrides(client: TestClient, engine: FakeTemplateEngine) -> None:
    template_id = client.post(
        "/api/templates",
        files={"file": ("t.docx", DOCX_BYTES, DOCX_MEDIA_TYPE)},
    ).json()["template_id"]

    payload = [
        {"find": "可行性分析报告", "replace": "XX市智能化项目投标书", "mode": "fixed"},
        {"find": "便携心电图系统", "replace": "", "mode": "doc_title"},
    ]
    response = client.put(
        f"/api/templates/{template_id}/cover-overrides",
        json=payload,
    )
    assert response.status_code == 204
    overrides = engine.templates[template_id].cover_overrides
    assert len(overrides) == 2
    assert overrides[0].find == "可行性分析报告"
    assert overrides[0].mode.value == "fixed"
    assert overrides[1].mode.value == "doc_title"


# ---------------------------------------------------------------------------
# Render / job lifecycle
# ---------------------------------------------------------------------------


def test_render_returns_job_and_download_url(
    client: TestClient, pipeline: FakePipeline, settings: Settings
) -> None:
    payload = render_once(client, doc_title="XX市智能化项目投标书")

    assert payload["download_url"] == f"/api/jobs/{payload['job_id']}/download"
    assert payload["filename"] == OUTPUT_FILENAME
    assert payload["elapsed_ms"] == 123
    assert payload["ttl_seconds"] == 60
    assert payload["warnings"] == ["fast_markdown 未启用"]
    expires_at = datetime.fromisoformat(payload["expires_at"])
    assert timedelta(seconds=0) < expires_at - datetime.now(timezone.utc) <= timedelta(seconds=60)

    request, workdir, job_id = pipeline.calls[0]
    assert request.doc_title == "XX市智能化项目投标书"
    assert workdir == settings.sandbox_root / job_id
    assert workdir.is_dir()


def test_get_job_reports_ready_state(client: TestClient) -> None:
    job_id = render_once(client)["job_id"]

    payload = client.get(f"/api/jobs/{job_id}").json()

    assert payload["job_id"] == job_id
    assert payload["state"] == JobState.READY.value
    assert payload["filename"] == OUTPUT_FILENAME
    assert payload["elapsed_ms"] == 123


def test_download_streams_the_docx(client: TestClient) -> None:
    job_id = render_once(client)["job_id"]

    response = client.get(f"/api/jobs/{job_id}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == DOCX_MEDIA_TYPE
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "filename*=UTF-8''%E6%8A%95%E6%A0%87%E6%96%87%E4%BB%B6.docx" in disposition
    assert response.content == DOCX_BYTES


def test_download_closes_the_resident_document_first(
    tmp_path: Path, engine: FakeTemplateEngine, pipeline: FakePipeline
) -> None:
    """CONTRACTS.md section 4: flush before a non-officecli read."""
    resident_settings = make_settings(tmp_path, no_auto_resident=False)
    runner = FakeRunner()
    with TestClient(
        build_app(resident_settings, engine=engine, pipeline=pipeline, runner=runner)
    ) as client:
        job_id = render_once(client)["job_id"]
        response = client.get(f"/api/jobs/{job_id}/download")

    assert response.status_code == 200
    assert runner.closed == [resident_settings.sandbox_root / job_id / OUTPUT_FILENAME]


def test_destroy_job_shreds_the_sandbox(
    client: TestClient, settings: Settings
) -> None:
    job_id = render_once(client)["job_id"]
    workdir = settings.sandbox_root / job_id
    assert workdir.is_dir()

    response = client.delete(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    report = response.json()
    assert report["job_id"] == job_id
    assert report["destroyed"] is True
    # source.md + the rendered .docx
    assert report["files_shredded"] == 2
    assert report["bytes_shredded"] > 0
    assert report["sandbox_exists_after"] is False
    assert not workdir.exists()


def test_no_docx_or_md_remains_after_destroy(client: TestClient, settings: Settings) -> None:
    """DoD #3: 数据零残留."""
    job_id = render_once(client)["job_id"]
    assert list(settings.sandbox_root.rglob("*.docx"))
    assert list(settings.sandbox_root.rglob("*.md"))

    client.delete(f"/api/jobs/{job_id}")

    assert list(settings.sandbox_root.rglob("*.docx")) == []
    assert list(settings.sandbox_root.rglob("*.md")) == []
    assert list(settings.sandbox_root.rglob("*")) == []


def test_download_after_destroy_is_gone(client: TestClient) -> None:
    job_id = render_once(client)["job_id"]
    client.delete(f"/api/jobs/{job_id}")

    response = client.get(f"/api/jobs/{job_id}/download")

    assert response.status_code == 410
    assert response.json()["code"] == "job_expired"


def test_get_job_after_destroy_shows_terminal_state(client: TestClient) -> None:
    job_id = render_once(client)["job_id"]
    client.delete(f"/api/jobs/{job_id}")

    payload = client.get(f"/api/jobs/{job_id}").json()

    assert payload["state"] == JobState.DESTROYED.value
    assert payload["destroyed_at"] is not None


def test_unknown_job_returns_404(client: TestClient) -> None:
    unknown = "deadbeefdeadbeefdeadbeefdeadbeef"

    for response in (
        client.get(f"/api/jobs/{unknown}"),
        client.get(f"/api/jobs/{unknown}/download"),
        client.delete(f"/api/jobs/{unknown}"),
    ):
        assert response.status_code == 404
        assert response.json()["code"] == "job_not_found"


def test_expired_job_returns_410(
    tmp_path: Path, engine: FakeTemplateEngine, pipeline: FakePipeline, runner: FakeRunner
) -> None:
    expiring = make_settings(tmp_path, job_ttl_seconds=0, reaper_interval_seconds=3600)
    with TestClient(build_app(expiring, engine=engine, pipeline=pipeline, runner=runner)) as client:
        job_id = render_once(client)["job_id"]
        job_response = client.get(f"/api/jobs/{job_id}")
        download_response = client.get(f"/api/jobs/{job_id}/download")

    assert job_response.status_code == 410
    assert job_response.json()["code"] == "job_expired"
    assert download_response.status_code == 410


def test_render_failure_maps_to_error_response_and_shreds(
    client: TestClient, pipeline: FakePipeline, settings: Settings
) -> None:
    pipeline.error = RenderError("目录生成失败", detail="toc add returned 1")

    response = client.post("/api/render", json={"markdown": "# 标题"})

    assert response.status_code == 500
    body = response.json()
    assert body == {
        "code": "render_error",
        "message": "目录生成失败",
        "detail": "toc add returned 1",
    }
    assert list(settings.sandbox_root.iterdir()) == []


def test_unexpected_pipeline_error_is_normalized(
    client: TestClient, pipeline: FakePipeline
) -> None:
    pipeline.error = ValueError("boom")

    response = client.post("/api/render", json={"markdown": "# 标题"})

    assert response.status_code == 500
    assert response.json()["code"] == "render_error"


def test_invalid_render_body_returns_error_envelope(client: TestClient) -> None:
    response = client.post("/api/render", json={"doc_title": "缺少 markdown"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_cors_allows_the_vite_dev_server(client: TestClient) -> None:
    response = client.options(
        "/api/render",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_download_exposes_content_disposition_to_the_browser(client: TestClient) -> None:
    job_id = render_once(client)["job_id"]

    response = client.get(
        f"/api/jobs/{job_id}/download", headers={"Origin": "http://localhost:5173"}
    )

    assert "content-disposition" in response.headers["access-control-expose-headers"].lower()


# ---------------------------------------------------------------------------
# Job store / reaper
# ---------------------------------------------------------------------------


@pytest.fixture
def store(settings: Settings) -> InMemoryJobStore:
    return InMemoryJobStore(EphemeralSandbox(settings), settings=settings)


def _result(job_id: str, workdir: Path) -> RenderResult:
    output = workdir / "out.docx"
    output.write_bytes(DOCX_BYTES)
    return RenderResult(job_id=job_id, filename="out.docx", output_path=output, elapsed_ms=5)


def test_job_store_state_machine(store: InMemoryJobStore) -> None:
    job = store.create_job()
    assert job.state is JobState.PENDING
    assert store.mark_running(job.job_id).state is JobState.RUNNING

    workdir = store._sandbox.create(job.job_id)
    ready = store.mark_ready(job.job_id, _result(job.job_id, workdir))
    assert ready.state is JobState.READY
    assert ready.filename == "out.docx"
    assert store.get_result(job.job_id).output_path == workdir / "out.docx"

    report = store.destroy_job(job.job_id)
    assert report.destroyed is True
    assert store.get_job(job.job_id).state is JobState.DESTROYED
    with pytest.raises(JobNotFoundError):
        store.get_result(job.job_id)


def test_job_store_marks_failure(store: InMemoryJobStore) -> None:
    job = store.create_job()

    failed = store.mark_failed(job.job_id, "officecli 退出码 1")

    assert failed.state is JobState.FAILED
    assert failed.error == "officecli 退出码 1"


def test_job_store_raises_for_unknown_and_expired(store: InMemoryJobStore) -> None:
    with pytest.raises(JobNotFoundError):
        store.get_job("unknown")
    assert store.peek_job("unknown") is None

    job = store.create_job(ttl_seconds=0)
    with pytest.raises(JobExpiredError):
        store.get_job(job.job_id)


def test_destroy_expired_sweeps_jobs_and_tombstones(store: InMemoryJobStore) -> None:
    live = store.create_job()
    store._sandbox.create(live.job_id)
    stale = store.create_job(ttl_seconds=0)
    stale_dir = store._sandbox.create(stale.job_id)
    (stale_dir / "leak.docx").write_bytes(DOCX_BYTES)

    reports = store.destroy_expired()

    assert stale.job_id in {report.job_id for report in reports}
    assert not stale_dir.exists()
    assert store.get_job(live.job_id).state is JobState.PENDING
    assert store.get_job(stale.job_id).state is JobState.DESTROYED

    # The tombstone is dropped on the next sweep (ttl_seconds=0).
    store.destroy_expired()
    with pytest.raises(JobNotFoundError):
        store.get_job(stale.job_id)


def test_destroy_all_shreds_every_live_job(store: InMemoryJobStore, settings: Settings) -> None:
    for _ in range(3):
        job = store.create_job()
        workdir = store._sandbox.create(job.job_id)
        (workdir / "out.docx").write_bytes(DOCX_BYTES)

    reports = store.destroy_all()

    assert len(reports) == 3
    assert all(report.destroyed for report in reports)
    assert list(settings.sandbox_root.rglob("*.docx")) == []


def test_reaper_sweeps_on_its_interval(store: InMemoryJobStore) -> None:
    job = store.create_job(ttl_seconds=0)
    workdir = store._sandbox.create(job.job_id)
    (workdir / "out.docx").write_bytes(DOCX_BYTES)

    async def scenario() -> None:
        reaper = JobReaper(store, interval_seconds=0.01)
        await reaper.start()
        assert reaper.running
        for _ in range(100):
            await asyncio.sleep(0.01)
            if not workdir.exists():
                break
        await reaper.stop()
        assert not reaper.running

    asyncio.run(scenario())

    assert not workdir.exists()
    assert store.get_job(job.job_id).state is JobState.DESTROYED


def test_shutdown_destroys_remaining_sandboxes(app: FastAPI, settings: Settings) -> None:
    with TestClient(app) as client:
        job_id = render_once(client)["job_id"]
        assert (settings.sandbox_root / job_id).is_dir()

    # Leaving the context manager runs the lifespan shutdown.
    assert not (settings.sandbox_root / job_id).exists()
    assert list(settings.sandbox_root.rglob("*.docx")) == []


def test_template_error_is_not_swallowed_by_the_finally_block(
    client: TestClient, engine: FakeTemplateEngine, settings: Settings
) -> None:
    def boom(source: Path, *, name: str | None = None, template_id: str | None = None):
        raise TemplateError("模板缺少 styles 部件", detail="no /styles part")

    engine.register_from_docx = boom  # type: ignore[method-assign]

    response = client.post(
        "/api/templates",
        files={"file": ("bad.docx", DOCX_BYTES, DOCX_MEDIA_TYPE)},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "模板缺少 styles 部件"
    assert list((settings.sandbox_root / "uploads").iterdir()) == []
