"""Markdown to DocumentAST parser implementation."""

from __future__ import annotations

import mistune

from docxforge.errors import MarkdownParseError
from docxforge.models import (
    ASTNode,
    CodeNode,
    DocumentAST,
    HeadingNode,
    ImageNode,
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
                nodes=[],
            )

        try:
            tokens, _ = self._markdown.parse(markdown)
        except Exception as exc:
            raise MarkdownParseError(f"Failed to parse markdown: {exc}") from exc

        children: list[ASTNode] = []
        extracted_title = doc_title

        for tok in tokens:
            nodes = self._convert_token_multi(tok)
            for node in nodes:
                if isinstance(node, HeadingNode) and node.level == 1 and not extracted_title:
                    extracted_title = node.content
                children.append(node)

        return DocumentAST(
            doc_title=extracted_title,
            template_id=template_id,
            nodes=children,
        )

    def _convert_token_multi(self, token: dict) -> list[ASTNode]:
        node = self._convert_token(token)
        if node:
            return [node]

        ttype = token.get("type")
        if ttype == "paragraph":
            sub_children = token.get("children", [])
            img_nodes: list[ASTNode] = []
            non_img_children: list[dict] = []

            for child in sub_children:
                if isinstance(child, dict) and child.get("type") == "image":
                    url = (
                        child.get("attrs", {}).get("url")
                        or child.get("src")
                        or child.get("attrs", {}).get("src", "")
                    )
                    alt_text = child.get("attrs", {}).get("alt")
                    alt = alt_text or self._extract_text(child.get("children", []))
                    if url:
                        img_nodes.append(ImageNode(src=url, alt=alt))
                else:
                    non_img_children.append(child)

            if img_nodes:
                text = self._extract_text(non_img_children).strip()
                if not text:
                    return img_nodes
                return [ParagraphNode(content=text)] + img_nodes

            text = self._extract_text(sub_children)
            if text == "---" or text == "***":
                return [ThematicBreakNode()]
            if "[pagebreak]" in text.lower():
                return [PageBreakNode()]
            return [ParagraphNode(content=text)]

        return []

    def _convert_token(self, token: dict) -> ASTNode | None:
        ttype = token.get("type")

        if ttype == "heading":
            level = token.get("attrs", {}).get("level", 1)
            raw_text = self._extract_text(token.get("children", []))
            return HeadingNode(level=level, content=raw_text)

        if ttype == "image":
            url = (
                token.get("attrs", {}).get("url")
                or token.get("src")
                or token.get("attrs", {}).get("src", "")
            )
            alt = token.get("attrs", {}).get("alt") or self._extract_text(token.get("children", []))
            return ImageNode(src=url, alt=alt) if url else None

        if ttype == "list":
            return self._convert_list(token)

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

    def _convert_list(self, token: dict) -> ListNode:
        ordered = token.get("attrs", {}).get("ordered", False)
        items: list[ListItem] = []
        self._collect_list_items(token, items, level=0)
        return ListNode(ordered=ordered, items=items)

    def _collect_list_items(
        self, token: dict, items: list[ListItem], *, level: int
    ) -> None:
        for it in token.get("children", []):
            if not isinstance(it, dict) or it.get("type") != "list_item":
                continue
            text_parts: list[object] = []
            nested_tokens: list[dict] = []
            for child in it.get("children", []):
                if isinstance(child, dict) and child.get("type") == "list":
                    nested_tokens.append(child)
                else:
                    text_parts.append(child)
            content = self._extract_text(text_parts).strip()
            items.append(ListItem(content=content, level=level))
            for nested in nested_tokens:
                self._collect_list_items(nested, items, level=level + 1)

    def _convert_table(self, token: dict) -> TableNode:
        children = token.get("children", [])
        headers: list[str] = []
        rows: list[list[str]] = []

        for child in children:
            ctype = child.get("type")
            if ctype == "table_head":
                # mistune 3: table_head children are table_cell directly (no
                # table_row wrapper), unlike table_body which nests rows.
                for cell in child.get("children", []):
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
