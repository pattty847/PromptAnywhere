"""Codex CLI provider adapter (Codex-first v1 path)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from typing import AsyncIterator

from prompt_anywhere.core.config import Config
from prompt_anywhere.core.providers.base import ProviderEvent
from prompt_anywhere.core.runner.cli_runner import CliRunner, RunnerEvent, RunnerResult


class CodexCliProvider:
    """Provider adapter that talks to Codex CLI via subprocess."""

    name = "codex-cli"

    def __init__(self, runner: CliRunner | None = None) -> None:
        self._runner = runner or CliRunner()
        self._cli = shutil.which("codex.cmd") or shutil.which("codex")
        self._config = Config()
        if not self._cli:
            raise FileNotFoundError("Codex CLI not found on PATH (expected `codex` or `codex.cmd`).")

    def _execution_mode(self) -> str:
        """Resolve execution mode from env/config with a safe fallback."""
        raw = str(
            os.environ.get("PROMPT_ANYWHERE_EXECUTION_MODE")
            or self._config.get("execution_mode", "tools-enabled")
        ).strip().lower()
        if raw in {"safe", "tools-enabled", "unrestricted"}:
            return raw
        return "tools-enabled"

    def _mode_flags(self, resume: bool) -> list[str]:
        """Return codex flags for current execution mode."""
        mode = self._execution_mode()
        if mode == "safe":
            if resume:
                return ["--json", "--skip-git-repo-check"]
            return [
                "--json",
                "--color",
                "never",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
            ]
        if mode == "unrestricted":
            return [
                "--json",
                "--dangerously-bypass-approvals-and-sandbox",
                "--skip-git-repo-check",
            ]
        # tools-enabled default: workspace-write with approvals via codex full-auto preset.
        return [
            "--json",
            "--full-auto",
            "--skip-git-repo-check",
        ]

    def _build_args(self, prompt: str, provider_session_id: str | None) -> list[str]:
        if provider_session_id:
            return [
                self._cli,
                "exec",
                "resume",
                *self._mode_flags(resume=True),
                provider_session_id,
                prompt,
            ]

        return [
            self._cli,
            "exec",
            *self._mode_flags(resume=False),
            prompt,
        ]

    @staticmethod
    def _parse_json_line(line: str) -> tuple[str | None, str | None]:
        """Parse one JSONL line into (delta_text, thread_id)."""

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return (None, None)
        if not isinstance(payload, dict):
            return (None, None)

        thread_id = payload.get("thread_id")
        normalized_thread = str(thread_id).strip() if isinstance(thread_id, str) and thread_id else None

        item = payload.get("item")
        if isinstance(item, dict):
            text = item.get("text")
            item_type = str(item.get("type") or "").lower()
            if isinstance(text, str) and text.strip() and ("message" in item_type or not item_type):
                return (text, normalized_thread)

        for key in ("text", "message", "content", "output_text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return (value, normalized_thread)

        return (None, normalized_thread)

    async def run(
        self,
        prompt: str,
        provider_session_id: str | None,
        abort_event: asyncio.Event,
    ) -> AsyncIterator[ProviderEvent]:
        """Run a single Codex turn and stream provider events."""

        args = self._build_args(prompt=prompt, provider_session_id=provider_session_id)
        discovered_session_id: str | None = provider_session_id

        async for event in self._runner.run(args, timeout_sec=120, abort_event=abort_event):
            if isinstance(event, RunnerEvent):
                if event.stream != "stdout":
                    continue

                text, thread_id = self._parse_json_line(event.line)
                if thread_id and thread_id != discovered_session_id:
                    discovered_session_id = thread_id
                    yield ProviderEvent(kind="meta", provider_session_id=discovered_session_id)

                if text:
                    yield ProviderEvent(kind="delta", text=text)
                continue

            if isinstance(event, RunnerResult):
                if event.returncode != 0:
                    detail = event.stderr_tail.strip() or event.stdout_tail.strip() or "unknown codex error"
                    raise RuntimeError(f"Codex CLI failed (exit={event.returncode}): {detail}")
                yield ProviderEvent(kind="final", provider_session_id=discovered_session_id)
