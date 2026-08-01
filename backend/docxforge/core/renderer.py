import base64
import hashlib
import re
import tempfile
from pathlib import Path

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

BASE64_IMAGE_PATTERN = re.compile(
    r"^data:image/(?P<ext>[a-zA-Z0-9]+);base64,(?P<data>.+)$", re.DOTALL
)


def resolve_image_source(
    src: str,
    *,
    workdir: Path | None = None,
    base_dir: str | Path | None = None,
) -> str:
    """Resolves Base64 data URIs, absolute paths, and relative paths to local files."""
    if not src:
        return src

    # 1. Base64 inline image
    b64_match = BASE64_IMAGE_PATTERN.match(src.strip())
    if b64_match:
        ext = b64_match.group("ext") or "png"
        raw_b64 = b64_match.group("data")
        try:
            img_bytes = base64.b64decode(raw_b64)
            sha = hashlib.md5(img_bytes).hexdigest()[:10]
            out_dir = workdir or Path(tempfile.gettempdir())
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / f"img_embed_{sha}.{ext}"
            if not target.exists():
                target.write_bytes(img_bytes)
            return str(target.resolve())
        except Exception:
            return src

    # 2. Local absolute path
    p = Path(src)
    if p.is_absolute():
        if p.exists():
            return str(p.resolve())

    # 3. Relative path with base_dir
    if base_dir:
        rel_target = Path(base_dir) / src
        if rel_target.exists():
            return str(rel_target.resolve())

    # 4. Fallback check
    if p.exists():
        return str(p.resolve())

    return src


class DefaultRenderer:
    """Production implementation of Renderer Protocol."""

    def build_commands(
        self,
        ast: DocumentAST,
        style_map: StyleMap,
        *,
        parent: str = "/body",
        workdir: Path | None = None,
        base_dir: str | Path | None = None,
    ) -> list[BatchItem]:
        items: list[BatchItem] = []

        for node in ast.nodes:
            items.extend(
                self._render_node(
                    node,
                    style_map,
                    parent=parent,
                    workdir=workdir,
                    base_dir=base_dir,
                )
            )

        return items

    def _render_node(
        self,
        node: ASTNode,
        style_map: StyleMap,
        *,
        parent: str,
        workdir: Path | None = None,
        base_dir: str | Path | None = None,
    ) -> list[BatchItem]:
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
            resolved_src = resolve_image_source(
                node.src, workdir=workdir, base_dir=base_dir
            )
            props = {"src": resolved_src}
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
