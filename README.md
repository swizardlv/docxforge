# DocXForge

基于 OfficeCLI 引擎的本地优先 Markdown → Pro-Word 国标级标书渲染工具。

需求见 `PRD.md`，跨模块开发约定见 `docs/CONTRACTS.md`。

## 依赖

- Python ≥ 3.10（推荐用 [`uv`](https://github.com/astral-sh/uv) 管理虚拟环境）
- Node ≥ 20 与 pnpm（前端）
- [`officecli`](https://github.com/iOfficeAI/OfficeCLI) ≥ 1.0.143

```bash
curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh | bash
officecli --version
```

## 后端

```bash
uv venv
uv pip install -e ".[dev]"
uv run uvicorn docxforge.api.main:app --reload --port 8000 --app-dir backend
uv run pytest backend/tests -q
```

## 前端

```bash
pnpm -C frontend install
pnpm -C frontend dev      # http://localhost:5173，/api 代理到 8000
```

## 架构

```
Markdown ──> MarkdownParser ──> DocumentAST
                                    │
              TemplateEngine ───────┤ StyleMap / PreparedBase
                                    ▼
                    Renderer + DocumentAssembler
                                    │  BatchItem[]
                                    ▼
                     OfficeCLIRunner (officecli batch)
                                    │
                                    ▼
                       封皮 + 自动目录 + 页眉页脚 .docx
```

隐私模型：每个渲染任务在独立沙箱目录中完成，默认 60 秒 TTL，到期或用户点击【立即销毁】后覆写并删除全部临时文件。
