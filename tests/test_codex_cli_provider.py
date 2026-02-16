from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prompt_anywhere.core.providers.codex_cli import CodexCliProvider  # noqa: E402


class TestCodexCliProviderArgs(unittest.TestCase):
    def _provider(self) -> CodexCliProvider:
        provider = CodexCliProvider.__new__(CodexCliProvider)
        provider._cli = "codex"
        return provider

    def test_build_args_for_fresh_exec(self) -> None:
        provider = self._provider()
        args = provider._build_args(prompt="hello", provider_session_id=None)
        self.assertEqual(
            args,
            [
                "codex",
                "exec",
                "--json",
                "--color",
                "never",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "hello",
            ],
        )

    def test_build_args_for_resume_exec(self) -> None:
        provider = self._provider()
        args = provider._build_args(prompt="continue", provider_session_id="thread-123")
        self.assertEqual(
            args,
            [
                "codex",
                "exec",
                "resume",
                "--json",
                "--dangerously-bypass-approvals-and-sandbox",
                "--skip-git-repo-check",
                "thread-123",
                "continue",
            ],
        )


if __name__ == "__main__":
    unittest.main()
