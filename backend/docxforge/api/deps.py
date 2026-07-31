"""Dependency providers for the API layer.

Two rules drive this module:

1. The API only ever depends on the *protocols* in
   :mod:`docxforge.interfaces`, never on a sibling module's concrete class.
2. Sibling modules (``core/template.py``, ``core/pipeline.py``,
   ``core/officecli.py``) are developed in parallel and may not exist yet, so
   they are imported lazily, inside the provider, and a missing implementation
   degrades to a clean 503 instead of an import-time crash.

Tests inject fakes with ``app.dependency_overrides[provider] = lambda: fake``.
"""

from __future__ import annotations

import importlib
from typing import Any

from fastapi import Request

from docxforge.config import Settings
from docxforge.errors import DocXForgeError
from docxforge.interfaces import JobStore, OfficeCLIRunner, RenderPipeline, Sandbox, TemplateEngine

__all__ = [
    "ComponentUnavailableError",
    "get_job_store",
    "get_officecli_runner",
    "get_render_pipeline",
    "get_sandbox",
    "get_settings_dep",
    "get_template_engine",
]


class ComponentUnavailableError(DocXForgeError):
    """A core component has not been wired into this build yet."""

    http_status = 503
    code = "component_unavailable"


#: Attribute names probed on a sibling module, in order. Factories come first
#: so an implementation can control its own construction.
_TEMPLATE_ENGINE_FACTORIES = (
    "create_template_engine",
    "get_template_engine",
    "build_template_engine",
    "TemplateEngine",
    "DocxTemplateEngine",
    "OfficeCLITemplateEngine",
    "DefaultTemplateEngine",
)
_PIPELINE_FACTORIES = (
    "create_pipeline",
    "create_render_pipeline",
    "get_pipeline",
    "build_pipeline",
    "RenderPipeline",
    "DocxRenderPipeline",
    "DefaultRenderPipeline",
    "Pipeline",
)
_RUNNER_FACTORIES = (
    "create_runner",
    "create_officecli_runner",
    "get_runner",
    "OfficeCLIRunner",
    "OfficeCLI",
    "SubprocessOfficeCLIRunner",
    "OfficeCLISubprocessRunner",
)


def _load_component(module_name: str, candidates: tuple[str, ...], protocol: Any) -> Any:
    """Instantiate the first zero-arg factory/class matching ``protocol``.

    Returns ``None`` when the module or a suitable implementation is missing.
    """
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None
    for attribute in candidates:
        factory = getattr(module, attribute, None)
        if factory is None or not callable(factory):
            continue
        try:
            instance = factory()
        except Exception:
            continue
        if isinstance(instance, protocol):
            return instance
    return None


def _cached_component(
    request: Request,
    state_key: str,
    module_name: str,
    candidates: tuple[str, ...],
    protocol: Any,
) -> Any:
    state = request.app.state
    cached = getattr(state, state_key, None)
    if cached is not None:
        return cached
    instance = _load_component(module_name, candidates, protocol)
    if instance is not None:
        setattr(state, state_key, instance)
    return instance


# -- application-owned singletons (created in the lifespan) -----------------


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_sandbox(request: Request) -> Sandbox:
    return request.app.state.sandbox


def get_job_store(request: Request) -> JobStore:
    return request.app.state.job_store


# -- lazily resolved sibling modules ---------------------------------------


def get_template_engine(request: Request) -> TemplateEngine:
    engine = _cached_component(
        request,
        "template_engine",
        "docxforge.core.template",
        _TEMPLATE_ENGINE_FACTORIES,
        TemplateEngine,
    )
    if engine is None:
        raise ComponentUnavailableError(
            "模板引擎尚未就绪，请稍后重试",
            detail=(
                "no TemplateEngine implementation found in docxforge.core.template; "
                f"expected one of {_TEMPLATE_ENGINE_FACTORIES}"
            ),
        )
    return engine


def get_render_pipeline(request: Request) -> RenderPipeline:
    pipeline = _cached_component(
        request,
        "render_pipeline",
        "docxforge.core.pipeline",
        _PIPELINE_FACTORIES,
        RenderPipeline,
    )
    if pipeline is None:
        raise ComponentUnavailableError(
            "渲染引擎尚未就绪，请稍后重试",
            detail=(
                "no RenderPipeline implementation found in docxforge.core.pipeline; "
                f"expected one of {_PIPELINE_FACTORIES}"
            ),
        )
    return pipeline


def get_officecli_runner(request: Request) -> OfficeCLIRunner | None:
    """Optional runner used for health probes and flush-before-read.

    Returns ``None`` instead of raising: neither caller is essential to a
    request succeeding.
    """
    return _cached_component(
        request,
        "officecli_runner",
        "docxforge.core.officecli",
        _RUNNER_FACTORIES,
        OfficeCLIRunner,
    )
