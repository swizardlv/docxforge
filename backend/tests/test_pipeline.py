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
