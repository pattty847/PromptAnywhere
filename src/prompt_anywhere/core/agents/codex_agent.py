"""Codex CLI agent implementation."""
from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Iterator, Optional

from prompt_anywhere.core.agents.base_agent import BaseAgent


class CodexAgent(BaseAgent):
    """Agent wrapper for Codex CLI."""

    def __init__(self) -> None:
        self._cli = shutil.which("codex.cmd") or shutil.which("codex")
        if not self._cli:
            raise FileNotFoundError(
                "Codex CLI not found. Install it and ensure `codex` is on PATH."
            )

    @property
    def name(self) -> str:
        """Agent name."""
        return "codex"

    def send_prompt(self, prompt: str, context: Optional[dict] = None) -> Iterator[str]:
        """Send a text prompt to Codex CLI and stream stdout lines."""
        del context  # Text-only backend for now.
        cmd = [self._cli, prompt]

        popen_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "bufsize": 1,
            "universal_newlines": True,
            "shell": False,
        }
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            popen_kwargs["startupinfo"] = startupinfo
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        process = subprocess.Popen(cmd, **popen_kwargs)
        for line in iter(process.stdout.readline, ""):
            if line:
                yield line
        process.wait()
        if process.returncode != 0:
            error_msg = process.stderr.read().strip()
            raise RuntimeError(f"Codex CLI error: {error_msg or 'unknown error'}")
