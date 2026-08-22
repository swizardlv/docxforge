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
from docxforge.models import PreparedBase, StyleMap, TemplateInfo


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
        info = TemplateInfo(
            template_id=tid,
            name=title,
            source_path=source,
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
        """Resolve the node-kind -> Word style mapping from the template's styles.

        The stored styles dump is a list of replay commands; every ``add style``
        entry carries the OOXML style id in ``props.id``. Standard ids (Heading1,
        Normal, ...) are kept verbatim; anything the template lacks falls back
        to the built-in default, which officecli accepts as an alias anyway.
        """
        style_map = StyleMap()
        if not template_id:
            return style_map

        config = self._read_config(template_id)
        if config is None:
            return style_map
        ids = self._extract_style_ids(config.get("styles") or [])
        if not ids:
            return style_map

        # Headings 1-6: keep the conventional id only when the template defines it.
        headings: dict[int, str] = {}
        for level, default_id in style_map.headings.items():
            headings[level] = default_id if default_id in ids else default_id
        style_map.headings = headings
        return style_map

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
