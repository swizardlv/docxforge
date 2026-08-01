"""DocumentAST to OfficeCLI batch items renderer implementation."""

from __future__ import annotations

from docxforge.models import (
    ASTNode,
    BatchItem,
    CodeNode,
    DocumentAST,
    HeadingNode,
    ImageNode,
    ListNode,
    ParagraphNode,
    StyleMap,
    TableNode,
)


class DefaultRenderer:
    """Production implementation of Renderer Protocol."""

    def build_commands(
        self,
        ast: DocumentAST,
        style_map: StyleMap,
        *,
        parent: str = "/body",
    ) -> list[BatchItem]:
        items: list[BatchItem] = []

        for node in ast.nodes:
            items.extend(self._render_node(node, style_map, parent=parent))

        return items

    def _render_node(self, node: ASTNode, style_map: StyleMap, *, parent: str) -> list[BatchItem]:
        items: list[BatchItem] = []

        if isinstance(node, HeadingNode):
            style_name = getattr(style_map, f"heading_{node.level}", f"Heading{node.level}")
            items.append(
                BatchItem(
                    command="add",
                    parent=parent,
                    type="paragraph",
                    props={"text": node.content, "style": style_name},
                )
            )

        elif isinstance(node, ParagraphNode):
            style_name = style_map.paragraph
            items.append(
                BatchItem(
                    command="add",
                    parent=parent,
                    type="paragraph",
                    props={"text": node.content, "style": style_name},
                )
            )

        elif isinstance(node, ListNode):
            style_name = style_map.list_ordered if node.ordered else style_map.list_bullet
            for item in node.items:
                items.append(
                    BatchItem(
                        command="add",
                        parent=parent,
                        type="paragraph",
                        props={"text": item.content, "style": style_name},
                    )
                )

        elif isinstance(node, TableNode):
            rows_count = len(node.rows) + (1 if node.headers else 0)
            cols_count = (
                len(node.headers) if node.headers else (len(node.rows[0]) if node.rows else 0)
            )
            if rows_count > 0 and cols_count > 0:
                tbl_style = style_map.table
                items.append(
                    BatchItem(
                        command="add",
                        parent=parent,
                        type="table",
                        props={
                            "rows": str(rows_count),
                            "cols": str(cols_count),
                            "style": tbl_style,
                        },
                    )
                )

        elif isinstance(node, CodeNode):
            style_name = style_map.code
            items.append(
                BatchItem(
                    command="add",
                    parent=parent,
                    type="paragraph",
                    props={"text": node.content, "style": style_name},
                )
            )

        elif isinstance(node, ImageNode):
            props = {"src": node.src}
            if node.alt:
                props["alt"] = node.alt
            items.append(
                BatchItem(
                    command="add",
                    parent=parent,
                    type="image",
                    props=props,
                )
            )

        return items
