"""Cover, TOC, Header/Footer, and settings injection implementation."""

from __future__ import annotations

from docxforge.models import (
    BatchItem,
    CoverOptions,
    HeaderFooterOptions,
    PreparedBase,
    TocOptions,
)


class DefaultDocumentAssembler:
    """Production implementation of DocumentAssembler Protocol."""

    def cover_commands(self, options: CoverOptions, base: PreparedBase) -> list[BatchItem]:
        items: list[BatchItem] = []
        if not options.enabled:
            return items

        for find_text, replace_text in options.replacements.items():
            items.append(
                BatchItem(
                    command="set",
                    path="/body",
                    props={"find": find_text, "replace": replace_text},
                )
            )

        return items

    def toc_commands(self, options: TocOptions, base: PreparedBase) -> list[BatchItem]:
        items: list[BatchItem] = []
        if not options.enabled:
            return items

        items.append(
            BatchItem(
                command="add",
                parent="/",
                type="toc",
                props={
                    "levels": options.levels,
                    "hyperlinks": "true" if options.hyperlinks else "false",
                    "pagenumbers": "true" if options.page_numbers else "false",
                },
            )
        )
        return items

    def header_footer_commands(
        self, options: HeaderFooterOptions, base: PreparedBase
    ) -> list[BatchItem]:
        items: list[BatchItem] = []
        if options.header_text:
            items.append(
                BatchItem(
                    command="add",
                    parent="/header",
                    type="paragraph",
                    props={"text": options.header_text, "style": "Header"},
                )
            )
        if options.footer_text:
            items.append(
                BatchItem(
                    command="add",
                    parent="/footer",
                    type="paragraph",
                    props={"text": options.footer_text, "style": "Footer"},
                )
            )
        return items

    def settings_commands(self, *, update_fields: bool) -> list[BatchItem]:
        items: list[BatchItem] = []
        if update_fields:
            items.append(
                BatchItem(
                    command="set",
                    path="/",
                    props={"updateFields": "true"},
                )
            )
        return items
