"""Template ingestion, extraction, and base document preparation."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from docxforge.config import Settings, get_settings
from docxforge.core.officecli import DefaultOfficeCLIRunner
from docxforge.errors import TemplateError, TemplateNotFoundError
from docxforge.interfaces import OfficeCLIRunner
from docxforge.models import (
    CoverItem,
    HeadingPreview,
    PreparedBase,
    StyleInfo,
    StyleMap,
    TemplateInfo,
)

#: Word style ids officecli accepts as built-in aliases even when the template's
#: styles part does not define them (see CONTRACTS.md section 4). The style-map
#: validation lets these through so a mapping can mix template styles with the
#: built-in fallbacks.
BUILTIN_STYLE_ALIASES = frozenset(
    {
        *(f"Heading{level}" for level in range(1, 7)),
        "Normal",
        "ListNumber",
        "ListBullet",
        "Quote",
        "HTMLPreformatted",
        "Caption",
        "TableGrid",
        "Title",
    }
)


class DefaultTemplateEngine:
    """Production implementation of TemplateEngine Protocol."""

    def __init__(
        self,
        settings: Settings | None = None,
        runner: OfficeCLIRunner | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.runner = runner or DefaultOfficeCLIRunner(self.settings)

    def _template_dir(self, template_id: str) -> Path:
        return self.settings.templates_dir / template_id

    def register_from_docx(
        self, source: Path, *, name: str | None = None, template_id: str | None = None
    ) -> TemplateInfo:
        if not source.exists():
            raise TemplateError(f"Source docx file not found: {source}")

        tid = template_id or f"tpl_{uuid.uuid4().hex[:12]}"
        tdir = self._template_dir(tid)
        tdir.mkdir(parents=True, exist_ok=True)

        target_docx = tdir / "template.docx"
        shutil.copy2(source, target_docx)

        # Dump extracted components via officecli dump. officecli 1.0.143 does
        # not support `/body/section[1]` (dump paths are limited to /, /body,
        # /body/p[N], /body/tbl[N], /theme, /settings, /numbering, /styles),
        # so the cover is derived from the leading run of body paragraphs.
        styles = self.runner.dump(target_docx, "/styles")
        numbering = self.runner.dump(target_docx, "/numbering")
        body = self.runner.dump(target_docx, "/body")
        cover_paragraph_count = self._count_leading_body_paragraphs(body)

        title = name or source.stem
        warnings: list[str] = []
        if cover_paragraph_count > 0:
            warnings.append(f"已按正文前 {cover_paragraph_count} 个段落识别为封皮")

        # Parse the /styles dump into structured StyleInfo list and infer the
        # node-kind → style-id mapping (StyleMap). Both are persisted in the
        # template config and used by the style-mapping UI.
        style_infos = self._parse_styles(styles)
        style_map = self._infer_style_map(style_infos)

        info = TemplateInfo(
            template_id=tid,
            name=title,
            source_path=source,
            styles=style_infos,
            style_map=style_map,
            has_cover=cover_paragraph_count > 0,
            has_numbering=bool(numbering),
            cover_paragraph_count=cover_paragraph_count,
            created_at=datetime.now(timezone.utc),
            warnings=warnings,
        )

        config_path = tdir / "template_config.json"
        config_data = {
            "info": info.model_dump(mode="json"),
            "styles": styles,
            "numbering": numbering,
            "cover": body,
        }
        config_path.write_text(
            json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return info

    @staticmethod
    def _count_leading_body_paragraphs(body_dump: list[dict]) -> int:
        """Count the leading run of ``add p`` commands in a /body dump."""
        count = 0
        for item in body_dump:
            if not isinstance(item, dict) or item.get("command") != "add":
                continue
            if item.get("type") == "p":
                count += 1
            else:
                break
        return count

    @staticmethod
    def _parse_styles(styles_dump: list[dict]) -> list[StyleInfo]:
        """Parse the /styles officecli dump replay-commands into StyleInfo objects.

        The dump is a list of ``add`` commands. Style definitions are ``add type=style``
        entries; their font/size/color/bold/italic/alignment attributes live in child
        commands (``w:rPr`` → ``w:rFonts`` / ``w:sz`` / ``w:color`` / ``w:b`` / ``w:i``,
        and ``w:pPr`` → ``w:spacing`` / ``w:jc``). The parser walks the flat list
        sequentially, treating commands between one ``type=style`` and the next (or
        end) as children of that style.
        """
        result: list[StyleInfo] = []
        current: dict[str, object] = {}

        for item in styles_dump:
            if not isinstance(item, dict):
                continue
            command = item.get("command")
            typ = item.get("type")
            props = item.get("props") or {}

            if command == "add" and typ == "style":
                if current:
                    result.append(StyleInfo(**current))
                current = {
                    "style_id": props.get("id") or "",
                    "name": props.get("name"),
                    "type": props.get("type"),
                    "based_on": props.get("basedOn"),
                }

            elif current:
                # Collect format properties from child commands.
                if typ == "w:rFonts":
                    # First available font (ascii > hAnsi > eastAsia)
                    font = (
                        props.get("w:ascii")
                        or props.get("w:hAnsi")
                        or props.get("w:eastAsia")
                    )
                    if font:
                        current.setdefault("font", font)
                elif typ == "w:sz":
                    try:
                        hval = int(props.get("w:val", "0"))
                        if hval:
                            current["size_pt"] = hval / 2.0
                    except (ValueError, TypeError):
                        pass
                elif typ == "w:color":
                    val = props.get("w:val")
                    if val:
                        current["color"] = val
                elif typ == "w:b":
                    current["bold"] = props.get("w:val", "1") != "0"
                elif typ == "w:i":
                    current["italic"] = props.get("w:val", "1") != "0"
                elif typ == "w:spacing":
                    line = props.get("w:line")
                    if line:
                        current["line_spacing"] = line
                elif typ == "w:jc":
                    val = props.get("w:val")
                    if val:
                        current["alignment"] = val

        if current:
            result.append(StyleInfo(**current))

        return result

    @staticmethod
    def _infer_style_map(styles: list[StyleInfo]) -> StyleMap:
        """Infer a StyleMap from the parsed style list by matching style names/IDs
        against conventional rendering roles.

        Headings (1-6) are matched first by numeric suffix in the style id or name
        (e.g. ``1``, ``heading 1``, ``Heading1``, ``标题 1``). Other roles are matched
        by keyword. Only the first match wins per role; unmatched styles are left
        unused but remain visible in the UI for manual assignment.
        """
        sm = StyleMap()
        # Build a lookup: style_id → StyleInfo
        by_id = {s.style_id: s for s in styles}

        # --- Headings 1-6 ---
        heading_map: dict[int, str] = {}
        for level in range(1, 7):
            candidates = []
            for sid, info in by_id.items():
                if info.style_id in heading_map.values():
                    continue  # already assigned
                lower_id = sid.lower()
                lower_name = (info.name or "").lower()
                # Match: id="1" / id="2" (numeric), or name contains "heading 1"/"标题 1"
                if sid == str(level):
                    candidates.append(sid)
                elif f"heading {level}" in lower_name:
                    candidates.append(sid)
                elif f"heading{level}" in lower_id:
                    candidates.append(sid)
                elif f"标题 {level}" in lower_name:
                    candidates.append(sid)
                elif level == 1 and "title" in lower_name and "标题" in lower_name:
                    candidates.append(sid)
            if candidates:
                # Prefer exact match by numeric id, then first candidate
                best = next((c for c in candidates if c == str(level)), candidates[0])
                heading_map[level] = best

        sm.headings = heading_map

        # --- Other roles (keyword match) ---
        role_patterns: list[tuple[str, str]] = [
            ("paragraph", "normal"),
            ("paragraph", "body text"),
            ("paragraph", "正文"),
            ("list_ordered", "list paragraph"),
            ("list_ordered", "列表"),
            ("list_bullet", "list bullet"),
            ("quote", "quote"),
            ("quote", "引用"),
            ("code", "html"),
            ("code", "代码"),
            ("caption", "caption"),
            ("caption", "题注"),
            ("table", "table grid"),
            ("table", "表格"),
            ("title", "title"),
            ("title", "封面"),
        ]

        assigned = set(sm.headings.values())
        _ROLE_ATTRS = ("paragraph", "list_ordered", "list_bullet", "quote",
                       "code", "caption", "table", "title")
        assigned_roles = {
            attr for attr in _ROLE_ATTRS
            if getattr(sm, attr) != getattr(StyleMap(), attr)
        }
        for attr, keyword in role_patterns:
            if attr in assigned_roles:
                # This role already has a concrete template style; the extra
                # keyword entry for the same role must not overwrite it.
                continue
            for sid, info in by_id.items():
                if sid in assigned:
                    continue
                lower_name = (info.name or "").lower()
                if keyword in lower_name:
                    setattr(sm, attr, sid)
                    assigned.add(sid)
                    assigned_roles.add(attr)
                    break

        return sm

    def list_templates(self) -> list[TemplateInfo]:
        if not self.settings.templates_dir.exists():
            return []

        templates: list[TemplateInfo] = []
        for tdir in self.settings.templates_dir.iterdir():
            if not tdir.is_dir():
                continue
            config_file = tdir / "template_config.json"
            if config_file.exists():
                try:
                    data = json.loads(config_file.read_text(encoding="utf-8"))
                    info_dict = data.get("info", {})
                    templates.append(TemplateInfo.model_validate(info_dict))
                except Exception:
                    continue
        templates.sort(
            key=lambda t: t.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True
        )
        return templates

    def get_template(self, template_id: str) -> TemplateInfo:
        config_file = self._template_dir(template_id) / "template_config.json"
        if not config_file.exists():
            raise TemplateNotFoundError(f"Template '{template_id}' not found")
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            return TemplateInfo.model_validate(data.get("info", {}))
        except Exception as exc:
            raise TemplateError(f"Failed to read template config for {template_id}") from exc

    def delete_template(self, template_id: str) -> None:
        tdir = self._template_dir(template_id)
        if not tdir.exists():
            raise TemplateNotFoundError(f"Template '{template_id}' not found")
        shutil.rmtree(tdir)

    def prepare_base(self, template_id: str | None, dest: Path) -> PreparedBase:
        dest.parent.mkdir(parents=True, exist_ok=True)

        if not template_id:
            self.runner.create(dest)
            return PreparedBase(
                path=dest,
                template_id=None,
                cover_paragraph_count=0,
                body_cleared=True,
            )

        template_info = self.get_template(template_id)
        src_docx = self._template_dir(template_id) / "template.docx"
        if not src_docx.exists():
            raise TemplateError(f"Template binary not found for '{template_id}'")

        shutil.copy2(src_docx, dest)

        # Clear sample body content, keeping the cover section when present.
        # IMPORTANT: We re-query after every removal because deleting an element
        # with a numeric index (e.g. /body/tbl[1]) renumbers all subsequent
        # indices of the same type — a snapshot of paths from before the loop
        # would point to wrong elements after the first structural removal.
        try:
            keep = template_info.cover_paragraph_count if template_info.has_cover else 0
            while True:
                body_data = self.runner.get(dest, "/body", depth=1)
                results = body_data.get("data", {}).get("results", [])
                children = results[0].get("children", []) if results else []
                target: str | None = None
                kept = 0
                for child in children:
                    path = child.get("path")
                    if not path or child.get("type") in ("sectPr", "section"):
                        continue
                    if kept < keep:
                        kept += 1
                        continue
                    target = path
                    break
                if target is None:
                    break
                try:
                    self.runner.remove(dest, target)
                except Exception:
                    # If the element resists deletion (e.g. a stray path) we
                    # must stop to avoid an infinite loop.
                    break
        except Exception:
            pass

        # Whether the template already carries header/footer parts. officecli
        # rejects adding a second 'default' header/footer in one section, so
        # the assembler must update the existing part instead.
        has_header = False
        has_footer = False
        try:
            has_header = bool(self.runner.query(dest, "header"))
            has_footer = bool(self.runner.query(dest, "footer"))
        except Exception:
            pass

        return PreparedBase(
            path=dest,
            template_id=template_id,
            cover_paragraph_count=template_info.cover_paragraph_count
            if template_info.has_cover
            else 0,
            body_cleared=True,
            has_header=has_header,
            has_footer=has_footer,
            style_map=template_info.style_map,
        )

    def style_map_for(self, template_id: str | None) -> StyleMap:
        """Resolve the node-kind -> Word style mapping for a template.

        Returns the persisted ``style_map`` from the template config (falling
        back to the default mapping for templates registered before style
        mapping existed, or when there is no template at all).
        """
        if not template_id:
            return StyleMap()
        config = self._read_config(template_id)
        if config is None:
            return StyleMap()
        info = config.get("info") or {}
        style_map_data = info.get("style_map")
        if isinstance(style_map_data, dict):
            try:
                return StyleMap.model_validate(style_map_data)
            except Exception:
                pass
        return StyleMap()

    def styles_for(self, template_id: str) -> dict:
        """Annotated style list + current mapping for the style-mapping UI.

        Returns a dict shaped like :class:`docxforge.models.TemplateStylesResponse`.
        """
        engine_info = self.get_template(template_id)
        style_map = engine_info.style_map
        # role <- style_id lookup built from the persisted map
        role_by_id: dict[str, str] = {}
        for level, sid in style_map.headings.items():
            if sid:
                role_by_id[sid] = f"heading{level}"
        role_attrs = {
            "paragraph": "paragraph",
            "list_ordered": "list_ordered",
            "list_bullet": "list_bullet",
            "quote": "quote",
            "code": "code",
            "caption": "caption",
            "table": "table",
            "title": "title",
        }
        for attr, role in role_attrs.items():
            sid = getattr(style_map, attr, None)
            if sid:
                role_by_id.setdefault(sid, role)

        entries = []
        for s in engine_info.styles:
            entries.append(
                {
                    "style_id": s.style_id,
                    "name": s.name,
                    "type": s.type,
                    "font": s.font,
                    "size_pt": s.size_pt,
                    "color": s.color,
                    "bold": s.bold,
                    "italic": s.italic,
                    "line_spacing": s.line_spacing,
                    "alignment": s.alignment,
                    "role": role_by_id.get(s.style_id, "unused"),
                }
            )
        return {
            "styles": entries,
            "style_map": style_map.model_dump(mode="json"),
        }

    def save_style_map(self, template_id: str, style_map: StyleMap) -> None:
        """Persist an updated style_map, validating every referenced style id."""
        valid_ids = {s.style_id for s in self.get_template(template_id).styles}
        referenced = set(style_map.headings.values())
        for attr in (
            "paragraph",
            "list_ordered",
            "list_bullet",
            "quote",
            "code",
            "caption",
            "table",
            "title",
        ):
            sid = getattr(style_map, attr)
            if sid:
                referenced.add(sid)
        # Built-in aliases (Heading1, Normal, ...) are always usable as a
        # fallback even when the template does not define them.
        missing = sorted((referenced - valid_ids) - BUILTIN_STYLE_ALIASES)
        if missing:
            raise TemplateError(
                "样式映射引用了不存在的样式",
                detail=", ".join(missing),
            )

        config = self._read_config(template_id)
        if config is None:
            raise TemplateNotFoundError(f"Template '{template_id}' not found")
        config.setdefault("info", {})["style_map"] = style_map.model_dump(mode="json")
        config_path = self._template_dir(template_id) / "template_config.json"
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _read_config(self, template_id: str) -> dict | None:
        config_file = self._template_dir(template_id) / "template_config.json"
        if not config_file.exists():
            return None
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _extract_style_ids(styles: list) -> set[str]:
        ids: set[str] = set()
        for item in styles:
            if not isinstance(item, dict) or item.get("command") != "add":
                continue
            if item.get("type") != "style":
                continue
            props = item.get("props") or {}
            sid = props.get("id") or props.get("styleId")
            if sid:
                ids.add(str(sid))
        return ids

    # -- template structure preview -------------------------------------------

    def preview_for(self, template_id: str) -> dict:
        """Assemble the template structure preview (cover / headings / hdr+ftr).

        Returns data shaped like :class:`docxforge.models.TemplatePreviewResponse`.
        """
        info = self.get_template(template_id)
        doc = self._template_dir(template_id) / "template.docx"

        # 1. Cover: leading body elements (paragraphs + tables), formatted.
        cover: list[CoverItem] = []
        try:
            body_data = self.runner.get(doc, "/body", depth=1)
            results = body_data.get("data", {}).get("results", [])
            children = results[0].get("children", []) if results else []
            for child in children:
                ctype = child.get("type")
                if ctype in ("sectPr", "section"):
                    continue
                if ctype == "paragraph":
                    cover.append(
                        CoverItem(
                            type="paragraph",
                            text=child.get("text") or "",
                            style=child.get("style"),
                        )
                    )
                elif ctype == "table":
                    rows = self._extract_table_rows(doc, child.get("path") or "")
                    cover.append(CoverItem(type="table", rows=rows))
                if len(cover) >= 6:
                    break
        except Exception:
            pass

        # 2. Headings: resolved format summary for levels 1-6.
        headings: list[HeadingPreview] = []
        for level in range(1, 7):
            sid = info.style_map.heading(level)
            style = next((s for s in info.styles if s.style_id == sid), None)
            headings.append(
                HeadingPreview(
                    level=level,
                    name=style.name if style else sid,
                    font=style.font if style else None,
                    size_pt=style.size_pt if style else None,
                    color=style.color if style else None,
                    bold=style.bold if style else None,
                    italic=style.italic if style else None,
                    sample=f"{'一二三四五六'[level - 1]}、标题示例",
                )
            )

        # 3. Header / footer text.
        header_text: str | None = None
        footer_text: str | None = None
        try:
            headers = self.runner.query(doc, "header")
            if headers:
                header_text = (headers[0].get("text") or "").strip() or None
            footers = self.runner.query(doc, "footer")
            if footers:
                footer_text = (footers[0].get("text") or "").strip() or None
        except Exception:
            pass

        return {
            "cover": [c.model_dump(mode="json") for c in cover],
            "headings": [h.model_dump(mode="json") for h in headings],
            "header_text": header_text,
            "footer_text": footer_text,
        }

    def _extract_table_rows(self, doc: Path, table_path: str) -> list[list[str]]:
        """Extract the cell text of a table for the cover preview."""
        rows: list[list[str]] = []
        try:
            table_data = self.runner.get(doc, table_path, depth=2)
            results = table_data.get("data", {}).get("results", [])
            table = results[0] if results else {}
            for row in table.get("children", []):
                cells = [c.get("text", "") for c in row.get("children", [])]
                if any(cells):
                    rows.append(cells)
        except Exception:
            pass
        return rows
