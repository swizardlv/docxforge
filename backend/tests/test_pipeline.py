"""End-to-end test for DefaultRenderPipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from docxforge.core.pipeline import DefaultRenderPipeline
from docxforge.models import RenderOptions, RenderRequest


@pytest.mark.officecli
def test_render_pipeline_e2e(sample_markdown: str, workdir: Path) -> None:
    pipeline = DefaultRenderPipeline()
    req = RenderRequest(
        markdown=sample_markdown,
        options=RenderOptions(),
    )

    res = pipeline.render(req, workdir=workdir, job_id="job_test_1")

    assert res.output_path.exists()
    assert res.node_count > 0
    assert res.elapsed_ms >= 0


@pytest.mark.officecli
def test_render_pipeline_with_image(workdir: Path) -> None:
    pipeline = DefaultRenderPipeline()
    b64_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="  # noqa: E501
    md_content = f"# 架构设计图\n\n以下为系统架构图：\n\n![架构图]({b64_img})\n\n设计说明已完成。\n"

    req = RenderRequest(
        markdown=md_content,
        options=RenderOptions(),
    )

    res = pipeline.render(req, workdir=workdir, job_id="job_test_img")

    assert res.output_path.exists()
    assert res.node_count >= 3
