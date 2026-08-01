# DocXForge 目录结构与使用指南

## 1. 为什么会有 5 个目录？

这 5 个目录是基于 **Git Worktree** 机制创建的。它们共享同一个 Git 仓库，但分别挂载了不同的分支，便于并行开发与隔离：

1. `/Users/swizard/code/docxforge` （**主目录，`main` 分支**）
   - **作用**：项目的核心主干。目前所有模块的代码（后端 API、渲染引擎、模板引擎、前端应用）均已合并到这里。
   - **推荐日常使用此目录**。

2. `/Users/swizard/code/docxforge-api` （`feat/api` 分支）
   - **作用**：专用于 FastAPI 路由与内存沙箱（Sandbox）模块的独立开发。

3. `/Users/swizard/code/docxforge-engine` （`feat/engine` 分支）
   - **作用**：专用于 OfficeCLI 命令封装与模板配置提取模块的独立开发。

4. `/Users/swizard/code/docxforge-renderer` （`feat/renderer` 分支）
   - **作用**：专用于 Markdown AST 解析与渲染管道（RenderPipeline）的独立开发。

5. `/Users/swizard/code/docxforge-frontend` （`feat/frontend` 分支）
   - **作用**：专用于 Vue 3 + Vite 前端界面的独立开发。

---

## 2. 如何运行和使用系统

在主目录 `/Users/swizard/code/docxforge` 中即可完成所有功能的运行与测试：

### 启动后端 API 服务
```bash
cd /Users/swizard/code/docxforge
uv run uvicorn docxforge.api.main:app --reload --port 8000
```

### 启动前端 Dev 服务
```bash
cd /Users/swizard/code/docxforge/frontend
pnpm dev
```
启动后在浏览器打开 `http://localhost:5173` 即可体验系统。

### 运行全量单元测试
```bash
cd /Users/swizard/code/docxforge
uv run pytest backend/tests -q
```

---

## 3. Worktree 维护与清理建议

由于分支代码已合并到 `main` 分支：

- **保留模式**：若后续还需要并行分模块开发，可继续保留这 4 个子 Worktree 目录。
- **清理模式**：若希望回到单目录模式，可以在主目录输入以下指令移除多余的 Worktree 目录：
  ```bash
  cd /Users/swizard/code/docxforge
  git worktree remove ../docxforge-api
  git worktree remove ../docxforge-engine
  git worktree remove ../docxforge-renderer
  git worktree remove ../docxforge-frontend
  ```
