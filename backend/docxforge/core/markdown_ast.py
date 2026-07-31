"""Markdown to DocumentAST parser implementation."""

from __future__ import annotations

import mistune

from docxforge.errors import MarkdownParseError
from docxforge.models import (
    ASTNode,
    CodeNode,
    DocumentAST,
    HeadingNode,
    ListItem,
    ListNode,
    PageBreakNode,
    ParagraphNode,
    QuoteNode,
    TableNode,
    ThematicBreakNode,
)


class DefaultMarkdownParser:
    """Production implementation of MarkdownParser Protocol using mistune AST."""

    def __init__(self) -> None:
        self._markdown = mistune.create_markdown(renderer=None, plugins=["table"])

    def parse(
        self,
        markdown: str,
        *,
        doc_title: str | None = None,
        template_id: str | None = None,
    ) -> DocumentAST:
        if not markdown:
            return DocumentAST(
                doc_title=doc_title,
                template_id=template_id,
                children=[],
            )

        try:
            tokens, _ = self._markdown.parse(markdown)
        except Exception as exc:
            raise MarkdownParseError(f"Failed to parse markdown: {exc}") from exc

        children: list[ASTNode] = []
        extracted_title = doc_title

        for tok in tokens:
            node = self._convert_token(tok)
            if node:
                if isinstance(node, HeadingNode) and node.level == 1 and not extracted_title:
                    extracted_title = node.content
                children.append(node)

        return DocumentAST(
            doc_title=extracted_title,
            template_id=template_id,
            nodes=children,
        )

    def _convert_token(self, token: dict) -> ASTNode | None:
        ttype = token.get("type")

        if ttype == "heading":
            level = token.get("attrs", {}).get("level", 1)
            raw_text = self._extract_text(token.get("children", []))
            return HeadingNode(level=level, content=raw_text)

        if ttype == "paragraph":
            text = self._extract_text(token.get("children", []))
            if text == "---" or text == "***":
                return ThematicBreakNode()
            if "[pagebreak]" in text.lower():
                return PageBreakNode()
            return ParagraphNode(content=text)

        if ttype == "list":
            ordered = token.get("attrs", {}).get("ordered", False)
            items_tok = token.get("children", [])
            items: list[ListItem] = []
            for it in items_tok:
                it_text = self._extract_text(it.get("children", []))
                items.append(ListItem(content=it_text))
            return ListNode(ordered=ordered, items=items)

        if ttype == "table":
            return self._convert_table(token)

        if ttype == "block_code" or ttype == "code":
            code_text = token.get("raw", token.get("text", ""))
            lang = token.get("attrs", {}).get("info", None)
            return CodeNode(content=code_text, language=lang)

        if ttype == "block_quote":
            q_text = self._extract_text(token.get("children", []))
            return QuoteNode(content=q_text)

        if ttype == "thematic_break":
            return ThematicBreakNode()

        return None

    def _convert_table(self, token: dict) -> TableNode:
        children = token.get("children", [])
        headers: list[str] = []
        rows: list[list[str]] = []

        for child in children:
            ctype = child.get("type")
            if ctype == "table_head":
                for row_tok in child.get("children", []):
                    for cell in row_tok.get("children", []):
                        headers.append(self._extract_text(cell.get("children", [])))
            elif ctype == "table_body":
                for row_tok in child.get("children", []):
                    row_cells: list[str] = []
                    for cell in row_tok.get("children", []):
                        cell_txt = self._extract_text(cell.get("children", []))
                        row_cells.append(cell_txt)
                    rows.append(row_cells)

        return TableNode(headers=headers, rows=rows)

    def _extract_text(self, children: list[dict]) -> str:
        parts: list[str] = []
        for child in children:
            if isinstance(child, dict):
                if "raw" in child:
                    parts.append(child["raw"])
                elif "text" in child:
                    parts.append(child["text"])
                elif "children" in child:
                    parts.append(self._extract_text(child["children"]))
            elif isinstance(child, str):
                parts.append(child)
        return "".join(parts).strip()
