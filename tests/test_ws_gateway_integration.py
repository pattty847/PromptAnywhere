from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi import FastAPI, WebSocket
try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - optional test dependency (httpx)
    TestClient = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prompt_anywhere.core.orchestrator import ChatSendRequest  # noqa: E402
from prompt_anywhere.host.ws_server import CopeNetWsServer  # noqa: E402


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.last_request: ChatSendRequest | None = None

    async def send_chat(self, request: ChatSendRequest, emit):
        self.last_request = request
        await emit(
            {
                "runId": request.idempotency_key,
                "sessionKey": request.session_key,
                "seq": 1,
                "state": "delta",
                "message": {"role": "assistant", "content": "hello"},
            }
        )
        await emit(
            {
                "runId": request.idempotency_key,
                "sessionKey": request.session_key,
                "seq": 2,
                "state": "final",
                "message": {"role": "assistant", "content": "hello"},
            }
        )
        return {"runId": request.idempotency_key, "status": "ok"}

    def abort(self, session_key: str, run_id: str | None = None):
        return {"ok": True, "aborted": False, "runIds": []}

    def history(self, session_key: str, limit: int = 200):
        return []

    def list_sessions(self):
        return []

    def resolve_session(self, session_key: str):
        return None


class TestWsGatewayIntegration(unittest.TestCase):
    @unittest.skipIf(TestClient is None, "fastapi test client requires httpx")
    def test_connect_then_chat_send_streams_chat_events(self) -> None:
        orchestrator = _FakeOrchestrator()
        ws_server = CopeNetWsServer(orchestrator=orchestrator)

        app = FastAPI()

        @app.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket) -> None:
            await ws_server.handle(websocket)

        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                challenge = ws.receive_json()
                self.assertEqual(challenge.get("type"), "event")
                self.assertEqual(challenge.get("event"), "connect.challenge")

                ws.send_json(
                    {
                        "type": "req",
                        "id": "connect-1",
                        "method": "connect",
                        "params": {"auth": {"token": "dev-token"}},
                    }
                )
                connect_res = ws.receive_json()
                self.assertEqual(connect_res.get("type"), "res")
                self.assertEqual(connect_res.get("id"), "connect-1")
                self.assertTrue(connect_res.get("ok"))

                ws.send_json(
                    {
                        "type": "req",
                        "id": "send-1",
                        "method": "chat.send",
                        "params": {
                            "sessionKey": "session-1",
                            "message": "hello",
                            "idempotencyKey": "run-1",
                            "provider": "codex-cli",
                        },
                    }
                )

                send_res = ws.receive_json()
                self.assertEqual(send_res.get("type"), "res")
                self.assertEqual(send_res.get("id"), "send-1")
                self.assertTrue(send_res.get("ok"))
                self.assertEqual((send_res.get("payload") or {}).get("status"), "started")

                delta_event = ws.receive_json()
                final_event = ws.receive_json()
                self.assertEqual(delta_event.get("type"), "event")
                self.assertEqual(delta_event.get("event"), "chat")
                self.assertEqual((delta_event.get("payload") or {}).get("state"), "delta")
                self.assertEqual(final_event.get("type"), "event")
                self.assertEqual(final_event.get("event"), "chat")
                self.assertEqual((final_event.get("payload") or {}).get("state"), "final")

        self.assertIsNotNone(orchestrator.last_request)
        self.assertEqual(orchestrator.last_request.session_key, "session-1")
        self.assertEqual(orchestrator.last_request.idempotency_key, "run-1")


if __name__ == "__main__":
    unittest.main()
