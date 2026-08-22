# 样式角色映射 + 项目工作区 设计文档

> 日期：2026-08-22
> 状态：已批准（用户确认方案 A + 左侧文件浏览器布局）

## 1. 背景与目标

### 现状问题

1. 模板注册时通过 `officecli dump` 提取了 styles（352 条命令），但 `TemplateInfo.styles` 是空的——提取结果从未被解析成结构化样式清单。
2. `style_map_for()` 永远返回默认 `StyleMap`（`Heading1`/`Normal` 等 Word 内置别名），模板自定义样式 id（如 `"1"`、`"a"`、`"af3"`）从未被利用。
3. 页面布局是"单 Markdown → 单 Word"模型，但实际标书工作流是"一个模板 + 多个 Markdown 文件 → 多个 Word"。

### 目标

1. **样式角色映射**：模板注册后展示其全部样式清单，自动识别每个样式扮演的渲染角色（标题1/正文/表格/页眉…），用户可调整角色映射并持久保存，渲染时按新映射生效。
2. **项目工作区（网页版，会话内）**：左侧文件浏览器组织多个 Markdown 文件，模板与样式映射全局共享；网页版文件列表仅会话内（符合隐私定位），桌面版（Tauri）后续持久化。

## 2. 范围与非目标

### 范围内
- 后端：模板样式解析、角色自动推断、`GET/PUT` 样式映射 API、`style_map_for` 读取持久化映射
- 前端：样式映射面板（卡片 + 角色下拉 + 保存）、左侧文件浏览器布局调整、批量导出
- 测试：解析/推断/API/前端组件

### 范围外（明确不做）
- 字体/字号/颜色等属性**编辑**（本期只读展示，用户已确认不是优先需求）
- 网页版项目文件持久化（会话内；Tauri 版后续）
- 页眉/页脚角色的映射编辑（StyleMap 无对应字段，本期只读识别标注）

## 3. 架构与数据流

```
注册模板 → 解析 styles dump → StyleInfo[] + 自动推断 style_map → 存 template_config.json
                                                  ↓
用户编辑映射 → PUT /api/templates/{id}/style-map → 更新 config 中的 style_map
                                                  ↓
渲染 → style_map_for(template_id) → 读取 style_map → 传给 renderer 按新映射渲染
```

原则：**不动现有渲染链路**，只新增 style_map 的解析、编辑与读取能力。渲染时 `--prop style=<真实style_id>` 引用模板定义。

## 4. 后端设计

### 4.1 样式解析（`template.py` / `officecli.py`）

`register_from_docx` 中新增 `_parse_styles(styles_dump) -> list[StyleInfo]`：

- 遍历 dump 命令，`type == "style"` 的 `add` 命令生成一个 `StyleInfo`
- 从后续子命令提取格式属性：
  - `w:rFonts` → `w:ascii` / `w:eastAsia` → `font`
  - `w:sz` → `w:val`（half-points）→ `size_pt = val / 2`
  - `w:color` → `w:val` → `color`
  - `w:b` / `w:i` → `bold` / `italic`
  - `w:spacing` → `w:line` → `line_spacing`
  - `w:jc` → `w:val` → `alignment`
  - `w:basedOn` → `w:val` → `based_on`

`StyleInfo` 模型补充字段（向后兼容，均有默认值）：
```python
class StyleInfo(BaseModel):
    style_id: str
    name: str | None = None
    type: str | None = None          # paragraph / character / table / numbering
    based_on: str | None = None
    font: str | None = None
    size_pt: float | None = None
    color: str | None = None         # NEW
    bold: bool | None = None         # NEW
    italic: bool | None = None       # NEW
    line_spacing: str | None = None  # NEW
    alignment: str | None = None     # NEW
```

`TemplateInfo` 补 `style_map` 持久化：`register_from_docx` 把推断出的 `style_map` 存入 `info` 和 config。

### 4.2 角色自动推断（`template.py`）

`_infer_style_map(styles: list[StyleInfo]) -> StyleMap`：

按样式名/ID 关键字匹配（中英文，大小写不敏感）：
| 角色 | 匹配关键字 |
|------|-----------|
| heading1..6 | `heading 1`/`标题 1`/`Heading1` 等 |
| paragraph | `normal`/`正文`/`body text` |
| list_ordered / list_bullet | `list paragraph`/`列表段落`（有序/无序按结构，默认有序） |
| quote | `quote`/`引用` |
| code | `html preformatted`/`代码`/`html` |
| caption | `caption`/`题注` |
| table | `table grid`/`表格`/`table` |
| title | `title`/`标题`（非 heading 数字后缀） |

匹配顺序：headings 优先（1→6），再按其他角色；一个样式只映射一个角色，先到先得。未匹配的样式角色为 `unused`。

### 4.3 新增 API（`routes.py`）

**`GET /api/templates/{template_id}/styles`** → `TemplateStylesResponse`
```json
{
  "styles": [
    {
      "style_id": "1", "name": "heading 1", "type": "paragraph",
      "font": "Times New Roman", "size_pt": 16.0,
      "role": "heading1", "role_label": "标题 1"
    }
  ],
  "style_map": {
    "headings": {"1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6"},
    "paragraph": "a", "list_ordered": "af7", "list_bullet": "af7",
    "quote": "af0", "code": "af2", "caption": "af0", "table": "af3", "title": "af0"
  }
}
```
- `role` 枚举：`heading1~6 | paragraph | list_ordered | list_bullet | quote | code | caption | table | title | unused`
- 未知模板 → 404 `template_not_found`

**`PUT /api/templates/{template_id}/style-map`** → 204
- 请求体 = `StyleMap`（复用现有模型）
- 校验：`headings` 的每个值、各字段值必须存在于该模板 styles 清单；否则 400 `template_error`（detail 列出非法 id）
- 未知模板 → 404

**`GET /api/templates`** 不变（`TemplateInfo` 现含填充后的 styles 与 style_map）。

### 4.4 渲染消费（`template.py`）

`style_map_for(template_id)`：
- 有模板 → 读取 config 中持久化的 `style_map`（带默认兜底）
- 无模板 → 返回默认 `StyleMap()`
- 渲染器已支持任意 style id（`--prop style=<id>`），无需改 renderer。

## 5. 前端设计

### 5.1 页面布局调整（`App.vue`）

```
┌──────────────┬──────────────────────────────────────┐
│ 左侧面板       │  Markdown 编辑器                      │
│ 文件浏览器      │  （当前文件内容）                      │
│  📄 背景.md    ├──────────────────────────────────────┤
│  📄 方案.md    │  结构预览 | 导出 | 销毁区（原右侧）      │
│  📄 预算.md    │                                      │
│ [导入文件夹]    │                                      │
│               │                                      │
│ 模板: 标书模板  │                                      │
│ [样式映射]     │                                      │
└──────────────┴──────────────────────────────────────┘
```

- 左栏新组件 `ProjectSidebar.vue`：文件列表 + 模板选择 + 样式映射入口
- 原 `MarkdownEditor.vue` 的文件夹导入/多文件选择逻辑**上移**到 `ProjectSidebar`（`mdFiles` 状态移入 store）
- 右侧保留：编辑器、结构预览、导出（当前文件）、销毁区；新增"全部导出"按钮（会话内文件列表全部渲染打包 zip）

### 5.2 样式映射面板（`StyleMappingPanel.vue`）

- 抽屉式面板，模板选中后可从左侧"样式映射"按钮打开
- 样式卡片列表：样式名 + 类型徽标 + 只读格式信息（字体/字号）+ 角色下拉
- 角色下拉值来自 `role_label` 映射（标题1-6/正文/有序/无序/引用/代码/表格/标题页/不映射）
- 已占用角色在其它下拉中标记提示；保存成功/失败内联提示
- Mock 模式实现两个 API（`mock.ts`）

### 5.3 状态管理（`stores/forge.ts`）

新增：
- `projectFiles`（文件列表，替代 MarkdownEditor 内部 mdFiles）
- `selectedFileKey`
- `stylePanelOpen` / `templateStyles` / `styleMapDraft` / `stylesLoading` / `stylesSaving`
- actions：`importFolder()`（迁移自 MarkdownEditor）、`loadTemplateStyles(id)`、`saveStyleMap(id, map)`

### 5.4 类型与 API（`types/api.ts`、`api/http.ts`、`api/mock.ts`）

- `TemplateStylesResponse`、`StyleRole` 类型
- `getTemplateStyles(templateId)`、`saveStyleMap(templateId, styleMap)`

## 6. 错误处理

| 场景 | 行为 |
|------|------|
| 模板不存在 | 404 `template_not_found` |
| PUT 引用不存在样式 id | 400 `template_error`，detail 列出非法 id |
| 保存失败（网络） | 面板内联错误，不关闭 |
| 后端不可达 | 前端降级 Mock（现有 resolveApi 机制） |

## 7. 测试计划

### 后端（pytest）
- `test_template.py`：`_parse_styles` 解析字体/字号/颜色；`_infer_style_map` 中英文角色匹配；`style_map_for` 返回持久化映射
- `test_api.py`：GET /styles 200；PUT /style-map 204；PUT 非法 id 400；未知模板 404

### 前端
- `StyleMappingPanel` 渲染样式卡片与角色下拉；保存调用 PUT
- 布局：左栏文件列表渲染/切换文件；全部导出按钮存在

### 端到端（手动）
- 上传含自定义样式的模板 → 面板展示样式并自动标注角色 → 修改映射 → 渲染验证新映射生效

## 8. 实现顺序

1. 后端：`StyleInfo` 扩展 + `_parse_styles` + `_infer_style_map` + `register_from_docx` 填充
2. 后端：`GET/PUT` API + `style_map_for` 持久化读取
3. 后端测试
4. 前端：类型/API/Store 扩展
5. 前端：`ProjectSidebar` 布局调整（文件列表上移）
6. 前端：`StyleMappingPanel` + 模板入口
7. 前端测试 + 手动端到端验证
8. 提交并推送

## 9. 开放问题

- 无（已与用户确认：持久保存到模板、全部样式+关键样式标注、模板选择器旁按钮、样式卡片预览、方案 A、项目工作区会话内）
