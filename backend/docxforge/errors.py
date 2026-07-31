"""Shared exception hierarchy.

Every module raises these; the API layer maps them to HTTP status codes.
Do not invent new top-level exception bases - subclass ``DocXForgeError``.
"""

from __future__ import annotations


class DocXForgeError(Exception):
    """Base class for every DocXForge failure."""

    http_status: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_payload(self) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "detail": self.detail}


class OfficeCLIError(DocXForgeError):
    """An ``officecli`` subprocess failed or returned an error envelope."""

    http_status = 502
    code = "officecli_failed"

    def __init__(
        self,
        message: str,
        *,
        command: list[str] | None = None,
        exit_code: int | None = None,
        stderr: str | None = None,
        cli_code: str | None = None,
    ) -> None:
        super().__init__(message, detail=stderr)
        self.command = command or []
        self.exit_code = exit_code
        self.stderr = stderr
        self.cli_code = cli_code

    def to_payload(self) -> dict[str, object]:
        payload = super().to_payload()
        payload.update({"exit_code": self.exit_code, "cli_code": self.cli_code})
        return payload


class OfficeCLINotFoundError(OfficeCLIError):
    """The ``officecli`` binary could not be located."""

    http_status = 503
    code = "officecli_not_found"


class OfficeCLITimeoutError(OfficeCLIError):
    """An ``officecli`` invocation exceeded its timeout budget."""

    http_status = 504
    code = "officecli_timeout"


class TemplateError(DocXForgeError):
    """Template registration / extraction failed."""

    http_status = 400
    code = "template_error"


class TemplateNotFoundError(TemplateError):
    http_status = 404
    code = "template_not_found"


class MarkdownParseError(DocXForgeError):
    """Markdown source could not be converted into a DocumentAST."""

    http_status = 400
    code = "markdown_parse_error"


class RenderError(DocXForgeError):
    """The render pipeline failed to produce a document."""

    http_status = 500
    code = "render_error"


class JobNotFoundError(DocXForgeError):
    """The job does not exist, or its sandbox was already destroyed."""

    http_status = 404
    code = "job_not_found"


class JobExpiredError(DocXForgeError):
    """The job existed but its ephemeral TTL elapsed and data was shredded."""

    http_status = 410
    code = "job_expired"


class ValidationFailedError(DocXForgeError):
    """Generated document failed OpenXML validation."""

    http_status = 500
    code = "document_invalid"
