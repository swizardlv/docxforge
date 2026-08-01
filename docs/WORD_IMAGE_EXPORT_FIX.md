# 导出 Word 图片渲染缺失问题排查与修复报告

## 1. 根因分析

问题表现为：在 Web 前端 HTML 预览中图片能够正常显示，但导出 Word (`.docx`) 后图片丢失或无法看到。

导致该问题的 2 个核心缺陷：
1. **Markdown AST 提取缺陷 (`markdown_ast.py`)**：
   在 Mistune 语法树解析中，当图片段落包含不可见空白字符或独立块级图片时，先前的过滤条件误将段落判断为纯文本段落（`ParagraphNode`），未能成功提取为 `ImageNode`。
2. **OfficeCLI 引擎 Batch 命令类型名不符合规范 (`renderer.py`)**：
   在 Batch 命令生成时使用了 `type="image"`。根据 OfficeCLI 1.0 的官方 CLI 规范定义，添加图片的元素类型名称为 **`picture`**。由于类型名称不合规，导致 OfficeCLI 忽略了图片添加请求。

---

## 2. 修复方案

1. **修复 `markdown_ast.py`**：
   - 增加对独立 `type="image"` 块级 Token 的全解析支持。
   - 修正段落内图片抽取的判定，剔除干扰空白，保证任何形式的图片语法 `![alt](src)` 都能稳定转化为 `ImageNode`。
2. **修正 `renderer.py`**：
   - 将 Batch 命令对应的类型名称修正为符合 OfficeCLI 标准的 **`type="picture"`**。
   - 保证物理落盘的临时图片或关联路径无缝传送给 OfficeCLI 图形引擎并嵌入 Word 实体。
3. **补充端到端测试**：
   - 在 `test_pipeline.py` 中新增 `test_render_pipeline_with_image` 端到端集成测试，全面覆盖 Markdown -> AST -> OfficeCLI picture -> docx 的完整导出链路。

---

## 3. 校验结果

- **前端状态**：`pnpm lint` 0 告警，`pnpm build` 构建成功。
- **后端状态**：`74/74` 全量测试通过，覆盖包含图片生成的导出测试。
