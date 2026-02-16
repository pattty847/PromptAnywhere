"""CopeNet-backed session history for the UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def get_history_path() -> Path:
    """Return CopeNet session index path for compatibility with caller APIs."""
    return _get_copenet_index_path()

def _get_copenet_sessions_dir() -> Path:
    """Return the CopeNet sessions directory."""
    return Path.home() / ".prompt_anywhere" / "sessions"


def _get_copenet_index_path() -> Path:
    """Return CopeNet session index path."""
    return _get_copenet_sessions_dir() / "index.json"


def _load_copenet_index() -> list[dict[str, Any]]:
    """Load CopeNet session index entries from disk."""
    path = _get_copenet_index_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    sessions = data.get("sessions")
    if not isinstance(sessions, list):
        return []
    return [entry for entry in sessions if isinstance(entry, dict)]


def _load_copenet_messages(session_id: str) -> list[dict[str, str]]:
    """Load CopeNet transcript JSONL for one session id."""
    safe = "".join(ch for ch in session_id if ch.isalnum() or ch in ("-", "_", ".")).strip()
    if not safe:
        return []
    transcript_path = _get_copenet_sessions_dir() / f"{safe}.jsonl"
    if not transcript_path.exists():
        return []

    messages: list[dict[str, str]] = []
    try:
        for line in transcript_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            role = payload.get("role")
            content = payload.get("content")
            if isinstance(role, str) and isinstance(content, str):
                messages.append({"role": role, "content": content})
    except OSError:
        return []
    return messages


def _load_copenet_sessions() -> list[dict]:
    """Load CopeNet sessions and map to UI session payload shape."""
    sessions: list[dict] = []
    for entry in _load_copenet_index():
        session_key = str(entry.get("session_key") or entry.get("sessionKey") or "").strip()
        session_id = str(entry.get("session_id") or entry.get("sessionId") or "").strip()
        if not session_key or not session_id:
            continue
        created_at = str(entry.get("created_at") or entry.get("createdAt") or "")
        updated_at = str(entry.get("updated_at") or entry.get("updatedAt") or "")
        messages = _load_copenet_messages(session_id)
        sessions.append(
            {
                "id": session_key,
                "created_at": created_at,
                "updated_at": updated_at,
                "messages": messages,
                "_source": "copenet",
                "_session_id": session_id,
            }
        )
    return sessions


def load_sessions(path: Path) -> list[dict]:
    """Load session history from CopeNet stores only."""
    _ = path
    return _load_copenet_sessions()


def save_session(path: Path, session_payload: dict) -> None:
    """No-op: CopeNet transcript/session stores are the source of truth."""
    _ = (path, session_payload)


def load_session_by_id(path: Path, session_id: str) -> dict | None:
    """Load a saved session by ID. Returns session dict or None."""
    _ = path
    sessions = load_sessions(path)
    for session in sessions:
        if session.get("id") == session_id:
            return session
    return None
