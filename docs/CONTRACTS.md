# DocXForge 开发契约

四个模块并行开发。本文件是唯一的跨模块约定来源，改动共享文件前必须先同步。

## 1. 文件所有权

| 分支 | 拥有的文件 | 禁止修改 |
| --- | --- | --- |
| `feat/engine` | `backend/docxforge/core/officecli.py`、`core/template.py`、`backend/tests/test_officecli.py`、`backend/tests/test_template.py` | 其它模块文件 |
| `feat/renderer` | `core/markdown_ast.py`、`core/renderer.py`、`core/assembler.py`、`core/pipeline.py`、`backend/tests/test_markdown_ast.py`、`test_renderer.py`、`test_assembler.py`、`test_pipeline.py` | 其它模块文件 |
| `feat/api` | `backend/docxforge/api/*`、`core/sandbox.py`、`backend/tests/test_sandbox.py`、`test_api.py` | 其它模块文件 |
| `feat/frontend` | `frontend/**` | 任何 Python 文件 |

**共享只读文件**（`models.py`、`interfaces.py`、`config.py`、`errors.py`、`conftest.py`、`pyproject.toml`）：需要改动时先向 orchestrator 提出，由 orchestrator 统一改，避免合并冲突。仅在 `conftest.py` 中追加新 fixture 是允许的例外，但不得修改已有 fixture。

## 2. 依赖方向

```
api  ->  pipeline  ->  {parser, renderer, assembler, template}  ->  officecli runner
```

反向依赖禁止。跨模块只依赖 `interfaces.py` 中的 Protocol，不 import 兄弟模块的具体类。所有构造函数用依赖注入接收依赖，默认参数可以是 `None` 并在内部惰性构造。

## 3. HTTP API 契约

前端与 api 模块都以此为准，字段名不得擅自更改。

- `GET /api/health` -> `HealthResponse`
- `GET /api/templates` -> `TemplateListResponse`
- `POST /api/templates`（`multipart/form-data`，字段 `file`，可选 `name`）-> `TemplateInfo`
- `DELETE /api/templates/{template_id}` -> `204`
- `POST /api/render`（JSON body = `RenderRequest`）-> `RenderResponse`
- `GET /api/jobs/{job_id}` -> `JobInfo`
- `GET /api/jobs/{job_id}/download` -> docx 二进制流，`Content-Disposition: attachment`
- `DELETE /api/jobs/{job_id}` -> `DestroyReport`

错误响应统一为 `ErrorResponse`，HTTP 状态码取自 `DocXForgeError.http_status`。

后端开发端口固定 `8000`，前端 dev server 固定 `5173` 并把 `/api` 代理到 `8000`。

## 4. OfficeCLI 使用约定

已在本机验证：`officecli 1.0.143`。

- 路径是 1-based，shell 中必须引号包裹：`'/body/p[1]'`。
- 正文写入统一走 `officecli batch <file> --input <json>`，一次进程完成，这是 3 秒/100 页目标的前提。不要为每个节点起一次子进程。
- batch 默认原子：任一条失败则整批回滚。需要“尽力而为”时显式传 `--best-effort`。
- 段落：`add /body --type paragraph --prop text=... --prop style=Heading1`。
- 表格：`add /body --type table --prop rows=N --prop cols=M`，再逐单元格 `set '/body/tbl[k]/tr[i]/tc[j]'`；同一批 batch 内完成。
- 目录：`add / --type toc --prop levels=1-3 --prop hyperlinks=true --prop pagenumbers=true`（add/set 用小写 `pagenumbers`）。**不要**手写 TOC 域代码。
- 字段刷新：`set <file> / --prop updateFields=true`。macOS 上 `officecli refresh` 不能算页码，不要依赖它。
- 快速模式：`add / --type markdown --prop src=<file.md>`。有损（链接/图片降级为纯文本、单元格无内联格式），只用于 `RenderOptions.fast_markdown`。
- 文本值中 `\n` 会被当作新段落，`\v` 是段内换行。含 `$` 的文本用单引号，避免 shell 变量展开。
- 非 officecli 程序（Python 读文件、下载接口）读取前必须先 `close`/`save`，否则可能读到旧内容。测试环境已通过 `OFFICECLI_NO_AUTO_RESIDENT=1` 走直连模式。
- 不确定属性名时运行 `officecli help docx <element>`，不要猜。

## 5. 验收标准映射（DoD）

1. 样式继承 — `feat/engine` 负责证明模板 styles/numbering/theme 保留。
2. 目录可交互 — `feat/renderer` 负责证明 `/toc[1]` 存在且 `updateFields=true`。
3. 数据零残留 — `feat/api` 负责证明销毁后沙箱目录与文件均不存在。
4. 100 页 < 3 秒 — `feat/renderer` 负责性能测试，标记 `@pytest.mark.slow`。

## 6. 质量门槛

提交前每个分支都必须自测通过：

```bash
uv run pytest backend/tests -q
uv run ruff check backend
```

前端：

```bash
pnpm -C frontend build
pnpm -C frontend lint
```
