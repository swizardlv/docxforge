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

        # Page break between the cover section and the TOC/body.
        if options.page_break_after and base.cover_paragraph_count > 0:
            items.append(
                BatchItem(command="add", parent="/body", type="pagebreak", props={"type": "page"})
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

        # Page break between the TOC and the body content.
        if options.page_break_after:
            items.append(
                BatchItem(command="add", parent="/body", type="pagebreak", props={"type": "page"})
            )

        return items

    def header_footer_commands(
        self, options: HeaderFooterOptions, base: PreparedBase
    ) -> list[BatchItem]:
        items: list[BatchItem] = []
        if options.header_text:
            # A fresh document has no header part: create it first, then add
            # the paragraph inside it.
            items.append(
                BatchItem(
                    command="add",
                    parent="/",
                    type="header",
                    props={"type": "default"},
                )
            )
            items.append(
                BatchItem(
                    command="add",
                    parent="/header[1]",
                    type="paragraph",
                    props={"text": options.header_text, "style": "Header"},
                )
            )
        if options.footer_text:
            items.append(
                BatchItem(
                    command="add",
                    parent="/",
                    type="footer",
                    props={"type": "default"},
                )
            )
            items.append(
                BatchItem(
                    command="add",
                    parent="/footer[1]",
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
