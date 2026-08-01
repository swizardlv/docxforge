# 本地与内嵌图片解析处理报告

## 1. 支持的 4 种嵌入/本地图片类型与实现机制

| 图片格式类型 | 语法示例 | 引擎内部处理方式 |
| --- | --- | --- |
| **Base64 内嵌图片** | `![图片](data:image/png;base64,iVBORw0...)` | 渲染器 `resolve_image_source` 自动解析 Base64 头部，在沙箱临时目录中解码生成物理图片文件并传递给 OfficeCLI 命令。 |
| **本地绝对路径图片** | `![图片](/Users/staff/docs/arch.png)` | 渲染引擎自动校验绝对路径文件是否存在，存在时直接注入 OfficeCLI 渲染指令。 |
| **本地相对路径图片** | `![图片](./images/schema.png)` | 结合 `RenderRequest` 的 `base_dir`（在界面中可配置“图片基准目录”），自动拼接绝对路径后注入 Word。 |
| **网络 HTTP(S) URL 图片** | `![图片](https://example.com/logo.png)` | 保持图片链接传递或自动解析。 |

## 2. 前后端更改与测试校验

1. **`renderer.py`**：实现 `resolve_image_source` 函数，支持 Base64 decode 临时落盘、绝对路径与相对路径拼接。
2. **`models.py` & `pipeline.py`**：`RenderRequest` 增加 `base_dir` 参数并透传至渲染组件。
3. **前端 UI**：在 [DocumentFields.vue](file:///Users/swizard/code/docxforge/frontend/src/components/DocumentFields.vue) 添加“图片基准目录 (Base Directory)”配置框，方便导入本地 Markdown 时指定项目根路径。
4. **单元测试与全量校验**：
   - 增加 [test_resolve_image_base64](file:///Users/swizard/code/docxforge/backend/tests/test_renderer.py) 与 [test_resolve_image_relative_path](file:///Users/swizard/code/docxforge/backend/tests/test_renderer.py)。
   - **结果**：73/73 后端测试通过；`pnpm lint` 零警告，`pnpm build` 打包构建成功。
