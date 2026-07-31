PRD

Here is my take: 一份专门为 **Vibe Coding**（以 AI 编程助手/LLM 为核心驱动的快速开发模式）量身定制的 PRD。

在 Vibe Coding 模式下，PRD 的读者主要是 **AI 引擎（如 Cursor, Claude, Windsurf 等）** 和你这个 **Prompt 工程师/开发者**。因此，这份文档摒弃了传统大公司冗长的商业拉扯，直奔**系统架构、上下文约束、数据结构与 Prompt 驱动逻辑**。

---

# 📄 Product Requirement Document (PRD)

## 📌 项目名称：DocXForge (AI 标书与排版大师)

> **一句话定义**：一个基于 OfficeCLI 引擎的本地优先（Local-First）Markdown 转 Pro-Word 国标级标书渲染工具。

---

## 1. 项目目标与核心体验 (Product North Star)

* **核心目标**：解决 AI 生成内容（Markdown）落地为标准 Word 标书（带封皮、页眉页脚、自动目录、规范格式）的“最后一公里”痛点。
* **隐私核心**：采用 **Local-First (Tauri + Local OfficeCLI)** 架构，默认数据不离端，完全隔离隐私风险；同时提供极简网页版（Memory-only 沙箱 + 1 分钟物理销毁机制）。
* **开发范式**：Vibe Coding 友好。模块间高内聚低耦合，逻辑全以 CLI/API 声明式命令驱动，方便 AI Agent 分步构建与测试。

---

## 2. 用户工作流 (User Journey)

```
[用户输入 Markdown] 
        + 
[选择/提取 Word 模板 (.docx)] 
        │
        ▼
┌─────────────────────────────────────────┐
│ 1. 样式引擎解析: 提取/应用 styles.json    │
│ 2. 结构渲染: MD AST 转换 -> OfficeCLI 指令│
│ 3. 元素注入: 封皮/页眉页脚/自动目录(TOC)   │
└─────────────────────────────────────────┘
        │
        ▼
[一键导出 Pro-Word / 物理销毁临时沙箱]

```

---

## 3. 系统架构与技术栈 (Tech Stack)

| 层级           | 技术选型                            | 说明 / 给 AI 的约束                        |
| -------------- | ----------------------------------- | ------------------------------------------ |
| **客户端/UI**  | Tauri + Vue 3 + TailwindCSS         | 渲染编辑器与本地交互，禁止在前端存敏感数据 |
| **应用后端**   | FastAPI (Python 3.10+)              | 轻量胶水层，负责 AST 解析与子进程调度      |
| **解析引擎**   | `mistune` / `marko` (Python)        | 将 Markdown 稳健解析为抽象语法树 (AST)     |
| **Word 底座**  | `OfficeCLI` (.NET 二进制可执行文件) | 负责底层 OOXML 安全修改、样式提取与填充    |
| **运行时沙箱** | `/dev/shm` 或内存临时目录           | 网页版所有的操作仅在内存文件系统完成       |

---

## 4. 核心功能模块详细设计 (Feature Specifications)

### 模块 A：模板提取与管理 (`Template Module`)

* **功能需求**：
1. 支持用户上传任意 `*.docx` 参考样本。
2. 后端调用 `officecli dump`，提取 `/styles`, `/numbering`, `/theme`, `/body/section[1]` (封皮)。
3. 将提取结果序列化为 `template_config.json` 存入本地/内存。


* **CLI 指令映射**：
```bash
officecli dump target.docx /styles -o styles.json
officecli dump target.docx /numbering -o numbering.json
officecli dump target.docx /body/section[1] -o cover.json

```



### 模块 B：Markdown AST 转 OfficeCLI 渲染器 (`Renderer Module`)

* **功能需求**：
1. 接收 Markdown 文本并转换为 AST。
2. 复制干净空白模板后，将 `styles.json` 用 `raw-set` 灌入新文档。
3. 深度遍历 AST 节点，生成对应的 OfficeCLI 命令序列（见下表）：



| MD 节点类型         | 映射样式           | OfficeCLI 命令模板                                           |
| ------------------- | ------------------ | ------------------------------------------------------------ |
| `Heading (Level 1)` | `Heading1`         | `officecli add out.docx /body --type paragraph --prop text="{text}" --prop style=Heading1` |
| `Heading (Level 2)` | `Heading2`         | `officecli add out.docx /body --type paragraph --prop text="{text}" --prop style=Heading2` |
| `Paragraph`         | `Normal`           | `officecli add out.docx /body --type paragraph --prop text="{text}" --prop style=Normal` |
| `List Item`         | `List Number`      | `officecli add out.docx /body --type paragraph --prop text="{text}" --prop style="List Number"` |
| `Table`             | `CustomTableStyle` | `officecli add out.docx /body --type table --prop datasource={temp_csv} --prop style=CustomTable` |

### 模块 C：标书三大件注入 (`TOC & Header/Footer Module`)

* **功能需求**：
1. **封皮（Cover）**：注入 `cover.json` 节点，使用 `set --prop find="原标题" --prop text="新标题"` 动态替换字段。
2. **自动目录（TOC）**：在封皮与正文间追加分节符，并注入 TOC 域代码：
```bash
officecli add out.docx /body/paragraph[2] --type field --prop instruction="TOC \o \"1-3\" \h \z \u"

```


3. **强制刷新**：向文档追加打开时自动更新属性：
```bash
officecli set out.docx /settings --prop updateFields=true

```





### 模块 D：隐私与无痕销毁防护 (`Privacy & Ephemeral Storage`)

* **功能需求**：
1. **网页端**：启用 Cron 定时器与物理销毁模块。
2. 文件生成完成后，前端启动 60 秒倒计时。倒计时结束或用户点击【立即销毁】后，调用 `shred -u` 或 Python `os.remove` 彻底擦除内存/临时文件。
3. 前端显示明文安全提示：“*数据全流程在临时内存中计算，销毁倒计时已启动*”。



---

## 5. 数据结构与接口协议 (Data Contracts)

### AST 翻译转换接口规范 (Internal Python DTO)

```json
{
  "doc_title": "XX市智能化项目投标书",
  "template_id": "custom_template_001",
  "nodes": [
    {
      "type": "heading",
      "level": 1,
      "content": "一、 项目背景与需求分析"
    },
    {
      "type": "paragraph",
      "content": "本项目的核心目标是构建高质量的智能化响应系统..."
    },
    {
      "type": "table",
      "headers": ["序号", "模块", "工期"],
      "rows": [
        ["1", "需求调研", "5天"],
        ["2", "系统开发", "15天"]
      ]
    }
  ]
}

```

---

## 6. Vibe Coding 开发提示词与任务拆解 (Prompt Steps for AI)

在将本 PRD 喂给 Cursor/Claude 开启 Vibe Coding 时，按以下顺序下发 Prompt 任务：

### 任务 1：搭建 Backend 基础与 OfficeCLI 封装

> **Prompt:** "请基于 FastAPI 和 Python 建立一个服务项目。编写一个 `OfficeCLIRunner` 类，用 `subprocess` 封装对 `officecli` 可执行文件的调用。实现创建空白 docx、添加段落（带 style 参数）、添加表格的基础方法，并编写 pytest 单元测试。"

### 任务 2：实现 Markdown AST 解析器与映射逻辑

> **Prompt:** "请使用 `mistune` 库写一个 Markdown 解析器，将 Markdown 字符串转为我们定义好的 AST 节点树，然后循环调用 `OfficeCLIRunner` 将 AST 节点依次写入目标 Word 文档中，要求能正确映射 H1-H3、正文和列表。"

### 任务 3：实现模板 Dump 与注入模块

> **Prompt:** "实现一个 `TemplateEngine` 类。支持接收一个已有的 `template.docx`，用 `officecli dump` 提取 `/styles` 和 `/body/section[1]` 存为 json。在生成新文档时，先用 `raw-set` 将这部分 JSON 刷入新建的空白文档中。"

### 任务 4：实现自动目录与设置更新

> **Prompt:** "在文档解析流程中，在封皮与正文之间插入一个分页符和 TOC Field 域代码，并在设置中开启 `updateFields=true`。写一个测试用例，校验生成的文档双击打开时是否提示更新目录。"

### 任务 5：构建前端界面与内存销毁 UI

> **Prompt:** "用 Vue 3 + TailwindCSS 写一个双栏界面。左侧是 Markdown 编辑器和模板选择下拉框，右侧是预览与导出按钮。导出后显示一个 60 秒物理销毁倒计时组件与【立即销毁】API 触发按钮。"

---

## 7. 验收标准 (Definition of Done - DoD)

1. **样式继承率 100%**：使用自定 `template.docx` 转换出的 Word，其标题字体、行距、表格边框与模板完全一致。
2. **目录可交互**：生成的 Word 在 Office/WPS 中打开时，会自动弹框询问或自动更新最新目录与页码。
3. **数据零残留**：网页版环境在按下“物理销毁”后，临时目录中找不到任何 `*.docx` 或 `*.md` 源文件。
4. **命令行流畅**：整个 Markdown 到完整 Word 的生成过程耗时控制在 3 秒以内（在 100 页文本测试集下）。