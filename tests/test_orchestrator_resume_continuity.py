from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prompt_anywhere.core.orchestrator import ChatSendRequest, Orchestrator  # noqa: E402
from prompt_anywhere.core.providers.base import ProviderEvent  # noqa: E402
from prompt_anywhere.core.sessions.session_store import SessionStore  # noqa: E402
from prompt_anywhere.core.sessions.transcript_store import TranscriptStore  # noqa: E402


class _FakeProvider:
    name = "fake-provider"

    def __init__(self) -> None:
        self.received_provider_session_ids: list[str | None] = []

    async def run(self, prompt: str, provider_session_id: str | None, abort_event: asyncio.Event):
        self.received_provider_session_ids.append(provider_session_id)
        if provider_session_id is None:
            yield ProviderEvent(kind="meta", provider_session_id="thread-abc")
            yield ProviderEvent(kind="delta", text=f"first:{prompt}")
            yield ProviderEvent(kind="final", provider_session_id="thread-abc")
            return
        yield ProviderEvent(kind="delta", text=f"resume:{prompt}")
        yield ProviderEvent(kind="final", provider_session_id=provider_session_id)


class TestOrchestratorResumeContinuity(unittest.TestCase):
    def test_second_turn_resumes_with_saved_provider_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            session_store = SessionStore(path=root / "index.json")
            transcript_store = TranscriptStore(root_dir=root)
            orchestrator = Orchestrator(session_store=session_store, transcript_store=transcript_store)
            fake = _FakeProvider()
            orchestrator._providers["codex-cli"] = fake
            orchestrator._provider_init_errors.pop("codex-cli", None)

            async def _run() -> None:
                async def emit(_payload: dict) -> None:
                    return None

                result1 = await orchestrator.send_chat(
                    ChatSendRequest(
                        session_key="session-alpha",
                        message="hello",
                        idempotency_key="run-1",
                        provider="codex-cli",
                    ),
                    emit=emit,
                )
                result2 = await orchestrator.send_chat(
                    ChatSendRequest(
                        session_key="session-alpha",
                        message="again",
                        idempotency_key="run-2",
                        provider="codex-cli",
                    ),
                    emit=emit,
                )
                self.assertEqual(result1.get("status"), "ok")
                self.assertEqual(result2.get("status"), "ok")

            asyncio.run(_run())

            self.assertEqual(fake.received_provider_session_ids, [None, "thread-abc"])

            session = session_store.get("session-alpha")
            self.assertIsNotNone(session)
            self.assertEqual(session.provider_session_id, "thread-abc")

            history = orchestrator.history("session-alpha", limit=20)
            self.assertEqual(len(history), 4)
            self.assertEqual(history[0].get("role"), "user")
            self.assertEqual(history[1].get("role"), "assistant")
            self.assertEqual(history[2].get("role"), "user")
            self.assertEqual(history[3].get("role"), "assistant")


if __name__ == "__main__":
    unittest.main()
