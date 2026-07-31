"""Runtime configuration.

All values are overridable via ``DOCXFORGE_*`` environment variables, e.g.
``DOCXFORGE_JOB_TTL_SECONDS=120``.
"""

from __future__ import annotations

import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_sandbox_root() -> Path:
    """Ephemeral scratch root.

    Linux exposes a real RAM-backed filesystem at ``/dev/shm``. macOS does not,
    so we fall back to the OS temp dir; the ephemeral guarantee there is
    enforced by TTL + overwrite-on-delete in the sandbox module, not by the FS.
    """
    shm = Path("/dev/shm")
    if shm.is_dir():
        return shm / "docxforge"
    return Path(tempfile.gettempdir()) / "docxforge"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCXFORGE_", extra="ignore")

    # --- OfficeCLI ---
    officecli_bin: str = Field(default="officecli")
    command_timeout: float = Field(default=120.0, description="Seconds per officecli invocation")
    # Direct mode keeps the file on disk always current; the pipeline opts into
    # resident mode explicitly around a render for speed.
    no_auto_resident: bool = Field(default=True)

    # --- Storage ---
    sandbox_root: Path = Field(default_factory=_default_sandbox_root)
    templates_dir: Path = Field(default_factory=lambda: Path.home() / ".docxforge" / "templates")
    max_upload_mb: int = Field(default=50)

    # --- Privacy / ephemeral storage ---
    job_ttl_seconds: int = Field(default=60, description="Countdown before physical destruction")
    shred_passes: int = Field(default=1, description="Overwrite passes before unlink")
    reaper_interval_seconds: float = Field(default=5.0)

    # --- Rendering ---
    update_fields_on_open: bool = Field(default=True)
    validate_output: bool = Field(default=False)

    def resolve_officecli(self) -> str | None:
        """Absolute path to the officecli binary, or None when unavailable."""
        return shutil.which(self.officecli_bin)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
