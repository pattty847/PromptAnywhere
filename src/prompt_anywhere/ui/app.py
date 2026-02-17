"""Main GUI application coordinator"""
import os
import sys
import signal
import asyncio
import uuid
import subprocess
from typing import Optional
from threading import Event, Thread
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

# Import pynput-dependent core before PySide6 to avoid shibokensupport/six conflict
from prompt_anywhere.core.app import App

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtCore import Qt, QObject, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap, QCursor

from prompt_anywhere.ui.windows.result_window import ResultWindow
from prompt_anywhere.ui.windows.prompt_shell_window import PromptShellWindow
from prompt_anywhere.ui.services import GatewayClient, GatewayConfig
from prompt_anywhere.core.features import (
    GoogleSearchFeature, FileSearchFeature, BrowserFeature,
    TerminalFeature, MaximizeChatFeature, HistoryFeature,
    ScreenshotFeature, CustomizeFeature
)


class StreamSignals(QObject):
    """Signals for thread-safe agent streaming"""
    text_chunk = Signal(str)
    finished = Signal()
    error = Signal(str)
    run_started = Signal(str)


class GatewayWorker(Thread):
    """Background thread that streams responses from CopeNet gateway."""

    def __init__(
        self,
        client: GatewayClient,
        session_key: str,
        prompt: str,
        provider: str,
    ):
        super().__init__(daemon=True)
        self.client = client
        self.session_key = session_key
        self.prompt = prompt
        self.provider = provider
        self.signals = StreamSignals()
        self._cancel_event = Event()
        self._run_id = f"run-{uuid.uuid4().hex[:10]}"

    @property
    def run_id(self) -> str:
        return self._run_id

    def stop(self):
        """Request cancellation and best-effort remote abort."""
        self._cancel_event.set()

        def _abort() -> None:
            try:
                asyncio.run(self.client.abort(session_key=self.session_key, run_id=self._run_id))
            except Exception:
                # Best-effort path; streaming thread will surface final state if available.
                pass

        Thread(target=_abort, daemon=True).start()

    def run(self):
        """Connect to gateway and stream chat events."""
        try:
            asyncio.run(self._run_async())
        except Exception as e:
            self.signals.error.emit(str(e))

    async def _run_async(self) -> None:
        terminal_emitted = False

        async def on_started(run_id: str) -> None:
            if run_id:
                self._run_id = run_id
            self.signals.run_started.emit(self._run_id)

        async def on_event(payload: dict) -> None:
            nonlocal terminal_emitted
            if self._cancel_event.is_set():
                return
            state = str(payload.get("state") or "")
            if state == "delta":
                message = payload.get("message") or {}
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content:
                        self.signals.text_chunk.emit(content)
            elif state == "error":
                msg = str(payload.get("errorMessage") or "Unknown gateway error")
                self.signals.error.emit(msg)
                terminal_emitted = True
            elif state in {"final", "aborted"}:
                self.signals.finished.emit()
                terminal_emitted = True

        result = await self.client.stream_chat(
            session_key=self.session_key,
            message=self.prompt,
            idempotency_key=self._run_id,
            provider=self.provider,
            on_event=on_event,
            on_started=on_started,
        )
        if not terminal_emitted:
            status = str((result or {}).get("status") or "")
            if status in {"in_flight", "cached", "started", "ok"}:
                self.signals.finished.emit()


class HotkeySignals(QObject):
    """Signals for hotkey communication"""
    triggered = Signal()


class PromptAnywhereApp:
    """Main application coordinator"""
    _AGENT_TO_PROVIDER = {
        "codex": "codex-cli",
    }
    
    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Keep running when windows close
        self.shell_window: Optional[PromptShellWindow] = None
        self.result_window: Optional[ResultWindow] = None  # legacy (unused once drawer lands)
        self.worker: Optional[Thread] = None
        self.active_gateway_run_id: Optional[str] = None
        self.active_gateway_session_key: Optional[str] = None
        self.gateway_mode = self._is_gateway_mode_enabled()
        self.gateway_client: Optional[GatewayClient] = self._create_gateway_client()

        # Initialize core app (pure Python)
        self.core_app = App()
        self._enforce_gateway_agent_selection()

        # Initialize features
        self.features = {
            'google_search': GoogleSearchFeature(),
            'file_search': FileSearchFeature(),
            'browser': BrowserFeature(),
            'terminal': TerminalFeature(),
            'maximize_chat': MaximizeChatFeature(),
            'history': HistoryFeature(),
            'screenshot': ScreenshotFeature(),
            'customize': CustomizeFeature(),
        }

        # Create hotkey signals
        self.hotkey_signals = HotkeySignals()
        self.hotkey_signals.triggered.connect(self.show_prompt_window)

        # Register hotkey
        self.core_app.register_hotkey(self._on_hotkey_triggered)

        self.setup_system_tray()
        print(f"Gateway mode: {'ON' if self.gateway_client is not None else 'OFF'}")

    def _is_gateway_mode_enabled(self) -> bool:
        """Read gateway mode flag from env (defaults ON)."""
        raw = os.environ.get("PROMPT_ANYWHERE_USE_GATEWAY", "1").strip().lower()
        return raw not in {"0", "false", "off", "no"}

    def _create_gateway_client(self) -> Optional[GatewayClient]:
        """Instantiate gateway client when enabled."""
        if not self.gateway_mode:
            return None
        url = os.environ.get("PROMPT_ANYWHERE_GATEWAY_URL", "ws://127.0.0.1:17123/ws").strip()
        token = os.environ.get("PROMPT_ANYWHERE_GATEWAY_TOKEN", "dev-token").strip()
        try:
            return GatewayClient(GatewayConfig(url=url, token=token))
        except Exception as exc:
            print(f"Gateway client disabled: {exc}")
            return None
    
    def _on_hotkey_triggered(self):
        """Hotkey callback - must be thread-safe"""
        print("Hotkey triggered! Emitting signal...")
        self.hotkey_signals.triggered.emit()
    
    def setup_system_tray(self):
        """Create system tray icon"""
        # Create a simple icon (colored square)
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 120, 215))
        icon = QIcon(pixmap)
        
        self.tray_icon = QSystemTrayIcon(icon, self.app)
        self.tray_icon.setToolTip("PromptAnywhere - Ctrl+Alt+X")
        
        # Create tray menu
        tray_menu = QMenu()
        
        open_action = tray_menu.addAction("Open Prompt (Ctrl+Alt+X)")
        open_action.triggered.connect(self.show_prompt_window)

        tray_menu.addSeparator()

        gateway_health_action = tray_menu.addAction("Gateway Health Check")
        gateway_health_action.triggered.connect(self.on_gateway_health_check)

        gateway_start_action = tray_menu.addAction("Start Gateway Host")
        gateway_start_action.triggered.connect(self.on_gateway_start)

        tray_menu.addSeparator()
        
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.app.quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
    
    def on_tray_activated(self, reason):
        """Handle tray icon clicks"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left click
            self.show_prompt_window()
    
    def show_prompt_window(self):
        """Display PromptAnywhere shell window near the mouse cursor."""
        if not self.shell_window:
            self.shell_window = PromptShellWindow()
            self.shell_window.prompt_submitted.connect(self.process_prompt)
            self.shell_window.follow_up_submitted.connect(self.process_prompt)
            self.shell_window.feature_triggered.connect(self.handle_feature)
            self.shell_window.session_closed.connect(self.on_result_window_closed)
            self.shell_window.history_session_selected.connect(self.open_history_session)
            self.shell_window.agent_selected.connect(self.on_agent_selected)
            self.shell_window.stop_requested.connect(self.stop_streaming)

        self.shell_window.set_available_agents(self._gateway_supported_agents())
        self.shell_window.set_selected_agent(self.core_app.get_current_agent_name())

        # Position near mouse cursor, clamped to screen edges
        self._position_near_cursor(self.shell_window)

        self.shell_window.show()
        self.shell_window.raise_()
        self.shell_window.activateWindow()
        self.shell_window.focus_input()
        self.shell_window.set_streaming_state(False)

    def _position_near_cursor(self, window: PromptShellWindow) -> None:
        """Place the window centered on the cursor, clamped to screen bounds."""
        cursor = QCursor.pos()
        screen = window.screen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        w, h = window.width(), window.height()

        # Center on cursor
        x = cursor.x() - w // 2
        y = cursor.y() - h // 2

        # Clamp to screen edges with a small margin
        margin = 8
        x = max(avail.left() + margin, min(x, avail.right() - w - margin))
        y = max(avail.top() + margin, min(y, avail.bottom() - h - margin))

        window.move(x, y)
    
    @Slot(str, str)
    def handle_feature(self, feature_name: str, prompt: str):
        """Handle feature button clicks"""
        print(f"Feature triggered: {feature_name} with prompt: {prompt}")

        if feature_name == "history":
            self.show_history_window()
            return

        feature = self.features.get(feature_name)
        if not feature:
            print(f"Unknown feature: {feature_name}")
            return

        # Execute feature
        result = feature.execute(prompt)
        print(f"Feature result: {result}")

        # Handle special cases
        if result == "maximize_window" and self.shell_window:
            self.shell_window.open_drawer(animated=True)
            self.shell_window.show()
            self.shell_window.raise_()
            self.shell_window.activateWindow()
        elif result == "open_customize":
            print("Opening customize dialog (not implemented yet)")

    @Slot(str, object)
    def process_prompt(self, prompt, image_bytes):
        """Process submitted prompt"""
        print(f"Processing prompt: {prompt[:50]}...")

        # Route all transcript rendering into the shell drawer.
        if not self.shell_window:
            # Shouldn't happen, but keep it safe.
            self.show_prompt_window()

        chat = self.shell_window.result_widget
        chat.ensure_session()
        self.shell_window.show_chat_mode()

        chat.add_user_message(prompt)
        chat.start_assistant_message()
        chat.set_loading_text("Connecting to gateway...")
        self.shell_window.open_drawer(animated=True)
        self.shell_window.set_streaming_state(True)

        if self.gateway_client is None:
            error_text = (
                "Gateway mode is required. Start prompt-anywhere-host and set "
                "PROMPT_ANYWHERE_USE_GATEWAY=1."
            )
            chat.show_error(error_text)
            self.shell_window.set_streaming_state(False)
            QMessageBox.critical(self.shell_window, "Gateway Required", error_text)
            return

        if image_bytes is not None:
            error_text = "Image attachments are not supported in gateway mode yet."
            chat.show_error(error_text)
            self.shell_window.set_streaming_state(False)
            return

        provider = self._provider_for_selected_agent()
        if provider is None:
            model_name = self.core_app.get_current_agent_name()
            error_text = f"Model '{model_name}' is not wired to CopeNet yet."
            chat.show_error(error_text)
            self.shell_window.set_streaming_state(False)
            return

        session_key = chat.session_id or "default"
        self.active_gateway_session_key = session_key
        self.active_gateway_run_id = None
        self.worker = GatewayWorker(
            client=self.gateway_client,
            session_key=session_key,
            prompt=prompt,
            provider=provider,
        )
        self.worker.signals.run_started.connect(self.on_gateway_run_started)

        chat = self.shell_window.result_widget
        self.worker.signals.text_chunk.connect(self.on_stream_chunk)
        self.worker.signals.text_chunk.connect(chat.append_text)
        self.worker.signals.finished.connect(chat.set_finished)
        self.worker.signals.finished.connect(self.on_stream_finished)
        self.worker.signals.error.connect(chat.show_error)
        self.worker.signals.error.connect(self.on_stream_finished)
        self.worker.start()

    def _provider_for_selected_agent(self) -> str | None:
        """Map current model selection to CopeNet provider ids."""
        model_name = self.core_app.get_current_agent_name().strip().lower()
        return self._AGENT_TO_PROVIDER.get(model_name)

    def _gateway_supported_agents(self) -> list[str]:
        """Return model keys currently wired to CopeNet providers."""
        return list(self._AGENT_TO_PROVIDER.keys())

    def _enforce_gateway_agent_selection(self) -> None:
        """Force config onto a gateway-supported model selection."""
        current = self.core_app.get_current_agent_name().strip().lower()
        supported = self._gateway_supported_agents()
        if current in supported:
            return
        fallback = supported[0]
        self.core_app.set_default_agent(fallback)
        print(f"Gateway mode model lock: switched default model to '{fallback}'.")

    def _gateway_health_url(self) -> str:
        """Convert websocket gateway URL into HTTP /health URL."""
        if self.gateway_client is None:
            return "http://127.0.0.1:17123/health"
        parts = urlsplit(self.gateway_client._config.url)
        scheme = "https" if parts.scheme == "wss" else "http"
        return urlunsplit((scheme, parts.netloc, "/health", "", ""))

    def _is_gateway_healthy(self) -> tuple[bool, str]:
        """Probe gateway /health endpoint."""
        url = self._gateway_health_url()
        try:
            with urlopen(url, timeout=1.5) as resp:
                status = int(getattr(resp, "status", 0))
                if status == 200:
                    return True, f"Gateway is healthy at {url}"
                return False, f"Gateway health returned HTTP {status} at {url}"
        except Exception as exc:
            return False, f"Gateway health check failed at {url}: {exc}"

    def on_gateway_health_check(self) -> None:
        """Handle tray action for gateway liveness check."""
        ok, message = self._is_gateway_healthy()
        print(message)
        if ok:
            QMessageBox.information(self.shell_window, "Gateway Health", message)
        else:
            QMessageBox.warning(self.shell_window, "Gateway Health", message)

    def on_gateway_start(self) -> None:
        """Start gateway host process if health check is currently failing."""
        ok, message = self._is_gateway_healthy()
        if ok:
            QMessageBox.information(self.shell_window, "Gateway Host", message)
            return
        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = (
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
            subprocess.Popen(
                [sys.executable, "-m", "prompt_anywhere.host"],
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            QMessageBox.critical(self.shell_window, "Gateway Host", f"Failed to start host: {exc}")
            return
        QMessageBox.information(
            self.shell_window,
            "Gateway Host",
            "Started gateway host process. Run Gateway Health Check in a second to confirm.",
        )

    @Slot()
    def stop_streaming(self):
        """Stop active stream when user presses Stop in prompt panel."""
        if self.worker and hasattr(self.worker, "stop"):
            self.worker.stop()
        if self.shell_window:
            self.shell_window.set_streaming_state(False)

    @Slot()
    def on_stream_finished(self):
        """Reset send/stop state once streaming completes or errors."""
        self.active_gateway_run_id = None
        if self.shell_window:
            self.shell_window.set_streaming_state(False)

    @Slot(str)
    def on_stream_chunk(self, _chunk: str):
        """Update loading affordance once output begins streaming."""
        if self.shell_window:
            self.shell_window.result_widget.set_loading_text("Streaming response...")

    @Slot(str)
    def on_gateway_run_started(self, run_id: str):
        """Track gateway run id for aborts/debug."""
        self.active_gateway_run_id = run_id
        if self.shell_window:
            self.shell_window.result_widget.set_loading_text("Thinking...")

    def show_history_window(self):
        """Open history inside the shell drawer."""
        if not self.shell_window:
            self.show_prompt_window()
        chat = self.shell_window.result_widget
        chat.load_sessions()
        self.shell_window.set_history_sessions(chat.saved_sessions)
        self.shell_window.show_history_mode(animated=True)
        self.shell_window.show()
        self.shell_window.raise_()
        self.shell_window.activateWindow()

    def open_history_session(self, session_id: str):
        """Open a saved session in the result window."""
        if not self.shell_window:
            self.show_prompt_window()
        chat = self.shell_window.result_widget
        chat.load_session(session_id)
        self.shell_window.show_chat_mode()
        self.shell_window.open_drawer(animated=False)
        self.shell_window.show()

    def on_result_window_closed(self):
        """Refresh history window after session close."""
        if self.shell_window:
            chat = self.shell_window.result_widget
            chat.load_sessions()
            self.shell_window.set_history_sessions(chat.saved_sessions)

    @Slot(str)
    def on_agent_selected(self, agent_name: str):
        """Switch active agent from compact model dropdown."""
        normalized = str(agent_name).strip().lower()
        if normalized not in self._gateway_supported_agents():
            error_text = f"Model '{normalized}' is not wired to CopeNet yet."
            print(f"Agent switch blocked: {error_text}")
            if self.shell_window:
                self.shell_window.set_selected_agent(self.core_app.get_current_agent_name())
                QMessageBox.warning(self.shell_window, "Model Unavailable", error_text)
            return
        try:
            self.core_app.set_default_agent(normalized)
        except Exception as e:
            error_text = str(e)
            print(f"Agent switch failed: {error_text}")
            if self.shell_window:
                self.shell_window.set_selected_agent(self.core_app.get_current_agent_name())
                QMessageBox.warning(
                    self.shell_window,
                    "Model Switch Failed",
                    error_text,
                )
    
    def run(self):
        """Start application loop"""
        print("\nPromptAnywhere is running!")
        print("   Press Ctrl+Alt+X to open prompt window")
        print("   Press Ctrl+C to exit\n")

        return self.app.exec()


def main():
    """Main entry point for GUI application"""
    # Set up signal handler for Ctrl+C
    def signal_handler(sig, frame):
        print("\nShutting down PromptAnywhere...")
        QApplication.quit()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    app = PromptAnywhereApp()

    # Allow Ctrl+C to work by processing events periodically
    timer = QTimer()
    timer.timeout.connect(lambda: None)  # Wake up event loop
    timer.start(100)

    sys.exit(app.run())
