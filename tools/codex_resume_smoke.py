from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from typing import Any


def _run_codex(args: list[str]) -> tuple[int, list[dict[str, Any]], str]:
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    events: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return proc.returncode, events, proc.stderr.strip()


def _thread_id_from_events(events: list[dict[str, Any]]) -> str | None:
    for payload in events:
        value = payload.get("thread_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    for payload in events:
        if payload.get("type") == "thread.started":
            value = payload.get("thread_id")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _agent_text_from_events(events: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for payload in events:
        item = payload.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n".join(parts).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test codex exec + resume continuity.")
    parser.add_argument("--first-prompt", default="Reply with READY.")
    parser.add_argument("--second-prompt", default="Reply with CONTINUED.")
    ns = parser.parse_args()

    codex = shutil.which("codex.cmd") or shutil.which("codex")
    if not codex:
        print("ERROR: codex CLI not found on PATH.")
        return 2

    first_args = [
        codex,
        "exec",
        "--json",
        "--color",
        "never",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        ns.first_prompt,
    ]
    rc1, events1, err1 = _run_codex(first_args)
    thread_id = _thread_id_from_events(events1)
    answer1 = _agent_text_from_events(events1)
    if rc1 != 0 or not thread_id:
        print("ERROR: first run failed.")
        if err1:
            print(err1)
        return 1

    second_args = [
        codex,
        "exec",
        "resume",
        "--json",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        thread_id,
        ns.second_prompt,
    ]
    rc2, events2, err2 = _run_codex(second_args)
    thread_id_2 = _thread_id_from_events(events2)
    answer2 = _agent_text_from_events(events2)
    if rc2 != 0:
        print("ERROR: resume run failed.")
        if err2:
            print(err2)
        return 1

    print(f"thread_id_1={thread_id}")
    print(f"thread_id_2={thread_id_2 or '<none>'}")
    print(f"same_thread={(thread_id_2 == thread_id) if thread_id_2 else True}")
    print(f"answer_1={answer1 or '<empty>'}")
    print(f"answer_2={answer2 or '<empty>'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
