"""Code block utilities for PromptAnywhere UI."""

from __future__ import annotations

import re

FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\n(.*?)```", re.DOTALL)


def extract_fenced_code_blocks(text: str) -> list[str]:
    return [m.strip("\n") for m in FENCE_RE.findall(text or "")]
