"""Shared pytest fixtures.

Owned collectively - add fixtures here only when more than one test module
needs them. Tests that shell out to the real binary must request the
``officecli_bin`` fixture (it skips when unavailable) and be marked
``@pytest.mark.officecli``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

SAMPLE_MARKDOWN = """# 一、 项目背景与需求分析

本项目的核心目标是构建高质量的智能化响应系统，满足招标文件的全部技术要求。

## 1.1 建设目标

- 覆盖全部功能性需求
- 满足国标格式要求
- 支持自动目录与页眉页脚

## 1.2 实施计划

| 序号 | 模块 | 工期 |
| --- | --- | --- |
| 1 | 需求调研 | 5天 |
| 2 | 系统开发 | 15天 |

# 二、 技术方案

> 采用本地优先架构，数据默认不离端。

1. 样式引擎解析
2. 结构渲染
3. 元素注入
"""


@pytest.fixture(scope="session")
def officecli_bin() -> str:
    """Absolute path to officecli, skipping the test when it is not installed."""
    resolved = shutil.which(os.environ.get("DOCXFORGE_OFFICECLI_BIN", "officecli"))
    if not resolved:
        pytest.skip("officecli binary not found on PATH")
    return resolved


@pytest.fixture(scope="session", autouse=True)
def _direct_mode() -> Iterator[None]:
    """Run officecli in direct mode during tests.

    Resident processes keep documents in memory and defer the disk write,
    which makes assertions against files on disk racy.
    """
    previous = os.environ.get("OFFICECLI_NO_AUTO_RESIDENT")
    os.environ["OFFICECLI_NO_AUTO_RESIDENT"] = "1"
    yield
    if previous is None:
        os.environ.pop("OFFICECLI_NO_AUTO_RESIDENT", None)
    else:
        os.environ["OFFICECLI_NO_AUTO_RESIDENT"] = previous


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    """An isolated scratch directory for one test."""
    d = tmp_path / "work"
    d.mkdir()
    return d


@pytest.fixture
def sample_markdown() -> str:
    return SAMPLE_MARKDOWN


@pytest.fixture
def make_markdown() -> Callable[[int], str]:
    """Build a large markdown corpus for performance tests (DoD #4)."""

    def _make(sections: int) -> str:
        chunks: list[str] = []
        for i in range(1, sections + 1):
            chunks.append(f"# 第 {i} 章 章节标题")
            chunks.append(f"## {i}.1 小节标题")
            chunks.append("这是一段用于性能测试的正文内容，" * 8)
            chunks.append("- 要点一\n- 要点二\n- 要点三")
            chunks.append("| 列A | 列B |\n| --- | --- |\n| 1 | 2 |")
        return "\n\n".join(chunks)

    return _make


@pytest.fixture
def template_docx(officecli_bin: str, tmp_path: Path) -> Path:
    """A reference .docx carrying custom styles, used by template tests."""
    path = tmp_path / "template.docx"
    subprocess.run([officecli_bin, "create", str(path)], check=True, capture_output=True)
    subprocess.run(
        [
            officecli_bin, "add", str(path), "/body",
            "--type", "paragraph",
            "--prop", "text=投标文件封面标题",
            "--prop", "style=Title",
        ],
        check=True,
        capture_output=True,
    )
    return path
