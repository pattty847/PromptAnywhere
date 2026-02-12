"""Session load/save for chat history. Isolates file I/O from UI."""

import json
from datetime import datetime
from pathlib import Path


def get_history_path() -> Path:
    """Return path to the persistent chat sessions file."""
    base_dir = Path.home() / ".prompt_anywhere"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "chat_sessions.json"


def load_sessions(path: Path) -> list[dict]:
    """Load session history from disk. Returns list of session dicts."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("sessions"), list):
            return data.get("sessions", [])
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_session(path: Path, session_payload: dict) -> None:
    """Persist a session to disk (merge/update in existing file)."""
    sessions = load_sessions(path)
    session_id = session_payload.get("id")
    if not session_id:
        return

    updated = False
    for index, session in enumerate(sessions):
        if session.get("id") == session_id:
            sessions[index] = session_payload
            updated = True
            break

    if not updated:
        sessions.append(session_payload)

    try:
        path.write_text(
            json.dumps({"sessions": sessions}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def load_session_by_id(path: Path, session_id: str) -> dict | None:
    """Load a saved session by ID. Returns session dict or None."""
    sessions = load_sessions(path)
    for session in sessions:
        if session.get("id") == session_id:
            return session
    return None
