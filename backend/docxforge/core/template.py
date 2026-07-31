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

        # Dump extracted components via officecli dump
        styles = self.runner.dump(target_docx, "/styles")
        numbering = self.runner.dump(target_docx, "/numbering")
        cover = self.runner.dump(target_docx, "/body/section[1]")

        title = name or source.stem
        info = TemplateInfo(
            template_id=tid,
            name=title,
            source_path=source,
            has_cover=bool(cover),
            has_numbering=bool(numbering),
            created_at=datetime.now(timezone.utc),
        )

        config_path = tdir / "template_config.json"
        config_data = {
            "info": info.model_dump(mode="json"),
            "styles": styles,
            "numbering": numbering,
            "cover": cover,
        }
        config_path.write_text(
            json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return info

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

        # Clear sample body content (except section[1] if cover exists)
        try:
            body_elements = self.runner.query(dest, "/body/*")
            start_index = template_info.cover_paragraph_count if template_info.has_cover else 0
            for elem in body_elements[start_index:]:
                path = elem.get("path")
                if path:
                    try:
                        self.runner.remove(dest, path)
                    except Exception:
                        pass
        except Exception:
            pass

        return PreparedBase(
            path=dest,
            template_id=template_id,
            cover_paragraph_count=template_info.cover_paragraph_count
            if template_info.has_cover
            else 0,
            body_cleared=True,
            style_map=template_info.style_map,
        )

    def style_map_for(self, template_id: str | None) -> StyleMap:
        return StyleMap()
