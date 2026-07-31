"""Subprocess wrapper for the officecli binary."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from docxforge.config import Settings, get_settings
from docxforge.errors import (
    OfficeCLIError,
    OfficeCLINotFoundError,
    OfficeCLITimeoutError,
)
from docxforge.models import BatchItem, BatchOutcome


class DefaultOfficeCLIRunner:
    """Production implementation of OfficeCLIRunner Protocol."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _get_bin(self) -> str:
        bin_path = self.settings.resolve_officecli()
        if not bin_path:
            raise OfficeCLINotFoundError(
                f"Binary '{self.settings.officecli_bin}' was not found on PATH."
            )
        return bin_path

    def _run(
        self,
        args: list[str],
        *,
        timeout: float | None = None,
        check: bool = True,
        input_data: str | bytes | None = None,
    ) -> subprocess.CompletedProcess[str]:
        bin_path = self._get_bin()
        cmd = [bin_path] + args
        eff_timeout = timeout if timeout is not None else self.settings.command_timeout

        try:
            res = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=eff_timeout,
            )
        except FileNotFoundError as exc:
            raise OfficeCLINotFoundError(
                f"Failed to execute {cmd[0]}", command=cmd, stderr=str(exc)
            ) from exc
        except subprocess.TimeoutExpired as exc:
            stderr = exc.stderr if isinstance(exc.stderr, str) else None
            raise OfficeCLITimeoutError(
                f"officecli command timed out after {eff_timeout}s",
                command=cmd,
                stderr=stderr,
            ) from exc

        if check and res.returncode != 0:
            raise OfficeCLIError(
                f"officecli command failed with exit code {res.returncode}",
                command=cmd,
                exit_code=res.returncode,
                stderr=res.stderr.strip() if res.stderr else res.stdout.strip(),
            )
        return res

    def version(self) -> str:
        res = self._run(["--version"])
        return res.stdout.strip()

    def is_available(self) -> bool:
        return self.settings.resolve_officecli() is not None

    def create(self, doc: Path, *, locale: str | None = None, minimal: bool = False) -> None:
        args = ["create", str(doc)]
        if locale:
            args.extend(["--locale", locale])
        if minimal:
            args.append("--minimal")
        self._run(args)

    def add(
        self,
        doc: Path,
        parent: str,
        *,
        type: str,
        props: dict[str, str] | None = None,
        after: str | None = None,
        before: str | None = None,
        index: int | None = None,
    ) -> str:
        args = ["add", str(doc), parent, "--type", type]
        if props:
            for k, v in props.items():
                args.extend(["--prop", f"{k}={v}"])
        if after:
            args.extend(["--after", after])
        if before:
            args.extend(["--before", before])
        if index is not None:
            args.extend(["--index", str(index)])

        res = self._run(args)
        out = res.stdout.strip()
        # Parse path from output if formatted as JSON or string
        if out.startswith("{") and out.endswith("}"):
            try:
                data = json.loads(out)
                if isinstance(data, dict) and "path" in data:
                    return str(data["path"])
            except json.JSONDecodeError:
                pass
        return out

    def set(
        self,
        doc: Path,
        path: str,
        *,
        props: dict[str, str] | None = None,
        find: str | None = None,
        replace: str | None = None,
    ) -> None:
        args = ["set", str(doc), path]
        if props:
            for k, v in props.items():
                args.extend(["--prop", f"{k}={v}"])
        if find is not None:
            args.extend(["--find", find])
        if replace is not None:
            args.extend(["--replace", replace])
        self._run(args)

    def get(self, doc: Path, path: str = "/", *, depth: int | None = None) -> dict[str, Any]:
        args = ["get", str(doc), path, "--json"]
        if depth is not None:
            args.extend(["--depth", str(depth)])
        res = self._run(args)
        out = res.stdout.strip()
        if not out:
            return {}
        try:
            parsed = json.loads(out)
            return parsed if isinstance(parsed, dict) else {"result": parsed}
        except json.JSONDecodeError:
            return {"raw": out}

    def query(self, doc: Path, selector: str) -> list[dict[str, Any]]:
        args = ["query", str(doc), selector, "--json"]
        res = self._run(args)
        out = res.stdout.strip()
        if not out:
            return []
        try:
            parsed = json.loads(out)
            return parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            return []

    def remove(self, doc: Path, path: str) -> None:
        self._run(["remove", str(doc), path])

    def view(self, doc: Path, mode: str = "outline", *, extra_args: list[str] | None = None) -> str:
        args = ["view", str(doc), mode]
        if extra_args:
            args.extend(extra_args)
        res = self._run(args)
        return res.stdout

    def dump(self, doc: Path, path: str = "/", *, out: Path | None = None) -> list[dict[str, Any]]:
        args = ["dump", str(doc), path, "--json"]
        if out is not None:
            args.extend(["-o", str(out)])
        res = self._run(args, check=False)
        if res.returncode != 0:
            return []
        out_text = res.stdout.strip()
        if out and out.exists():
            content = out.read_text(encoding="utf-8")
            try:
                parsed = json.loads(content)
                return parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                return []
        if out_text:
            try:
                parsed = json.loads(out_text)
                return parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                return []
        return []

    def batch(
        self,
        doc: Path,
        items: list[BatchItem],
        *,
        best_effort: bool = False,
        stop_on_error: bool = False,
    ) -> BatchOutcome:
        if not items:
            return BatchOutcome(total=0, executed=0, failed=0, errors=[])

        payload = [item.model_dump(exclude_none=True) for item in items]
        raw_json = json.dumps(payload, ensure_ascii=False)

        args = ["batch", str(doc), "--json"]
        if best_effort:
            args.append("--best-effort")
        if stop_on_error:
            args.append("--stop-on-error")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(raw_json)
            tmp_path = Path(tmp.name)

        try:
            args.extend(["--input", str(tmp_path)])
            res = self._run(args, check=not best_effort)
            out = res.stdout.strip()

            executed = len(items)
            failed = 0
            errors: list[str] = []

            if out.startswith("{") or out.startswith("["):
                try:
                    res_data = json.loads(out)
                    if isinstance(res_data, dict):
                        executed = res_data.get("executed", executed)
                        failed = res_data.get("failed", 0)
                        errors = res_data.get("errors", [])
                except json.JSONDecodeError:
                    pass

            if res.returncode != 0 and best_effort:
                failed = failed or 1
                if res.stderr:
                    errors.append(res.stderr.strip())

            return BatchOutcome(total=len(items), executed=executed, failed=failed, errors=errors)
        finally:
            if tmp_path.exists():
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def raw_set(self, doc: Path, part: str, *, xpath: str, action: str, xml: str) -> None:
        args = [
            "raw-set",
            str(doc),
            part,
            "--xpath",
            xpath,
            "--action",
            action,
            "--xml",
            xml,
        ]
        self._run(args)

    def validate(self, doc: Path) -> list[str]:
        res = self._run(["validate", str(doc), "--json"], check=False)
        out = res.stdout.strip()
        if not out:
            return [] if res.returncode == 0 else [res.stderr.strip()]
        try:
            data = json.loads(out)
            if isinstance(data, list):
                return [str(item) for item in data]
            if isinstance(data, dict) and "issues" in data:
                return [str(i) for i in data["issues"]]
            return [str(data)]
        except json.JSONDecodeError:
            return [out]

    def open(self, doc: Path) -> None:
        self._run(["open", str(doc)])

    def save(self, doc: Path) -> None:
        self._run(["save", str(doc)])

    def close(self, doc: Path) -> None:
        self._run(["close", str(doc)])
