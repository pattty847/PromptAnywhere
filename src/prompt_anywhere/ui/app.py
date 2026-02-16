"""Main GUI application coordinator"""
import os
import sys
import signal
import time
import asyncio
import uuid
from typing import Optional
from threading import Event, Thread

# Import pynput-dependent core before PySide6 to avoid shibokensupport/six conflict
from prompt_anywhere.core.app import App

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtCore import Qt, QObject, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap, QCursor

from prompt_anywhere.ui.windows.result_window import ResultWindow
from prompt_anywhere.ui.windows.prompt_shell_window import PromptShellWindow
from prompt_anywhere.core.agents.base_agent import BaseAgent
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


class AgentWorker(Thread):
    """Background thread for agent calls"""
    
    def __init__(self, agent: BaseAgent, prompt: str, image_bytes=None):
        super().__init__(daemon=True)
        self.agent = agent
        self.prompt = prompt
        self.image_bytes = image_bytes
        self.signals = StreamSignals()
        self._cancel_event = Event()

    def stop(self):
        """Request cancellation of the active agent stream."""
        self._cancel_event.set()
    
    def run(self):
        """Run agent in background thread"""
        try:
            context = {'cancel_event': self._cancel_event}
            if self.image_bytes:
                context['image_bytes'] = self.image_bytes
            
            # Stream response from agent
            for chunk in self.agent.send_prompt(self.prompt, context):
                if self._cancel_event.is_set():
                    break
                self.signals.text_chunk.emit(chunk)
            
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))


class MockAgentWorker(Thread):
    """Background worker that streams fake text for UI iteration."""

    def __init__(self, prompt: str, image_bytes=None):
        super().__init__(daemon=True)
        self.prompt = prompt
        self.image_bytes = image_bytes
        self.signals = StreamSignals()
        self._cancel_event = Event()

    def stop(self):
        """Request cancellation of mock stream."""
        self._cancel_event.set()

    def run(self):
        """Stream mock chunks that resemble real output pacing."""
        try:
            attachment_note = " with screenshot context" if self.image_bytes else ""
            chunks = [
                "Mock mode is enabled.\n\n",
                f"I received your prompt{attachment_note}: ",
                f"\"{self.prompt[:120]}\".\n\n",
                "This is a simulated streaming response so you can test drawer layout, sizing, and animation quickly.\n\n",
                "Disable Mock Response Mode from the tray menu when you want real agent output again.",
            ]
            for chunk in chunks:
                if self._cancel_event.is_set():
                    break
                self.signals.text_chunk.emit(chunk)
                time.sleep(0.08)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))


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
    
    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Keep running when windows close
        self.shell_window: Optional[PromptShellWindow] = None
        self.result_window: Optional[ResultWindow] = None  # legacy (unused once drawer lands)
        self.worker: Optional[Thread] = None
        self.active_gateway_run_id: Optional[str] = None
        self.active_gateway_session_key: Optional[str] = None
        self.mock_response_mode = self._is_mock_mode_enabled_by_default()
        self.gateway_mode = self._is_gateway_mode_enabled()
        self.gateway_client: Optional[GatewayClient] = self._create_gateway_client()

        # Initialize core app (pure Python)
        self.core_app = App()

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
        print(f"Mock response mode: {'ON' if self.mock_response_mode else 'OFF'}")
        print(f"Gateway mode: {'ON' if self.gateway_client is not None else 'OFF'}")

    def _is_mock_mode_enabled_by_default(self) -> bool:
        """Read mock mode from environment (defaults ON for UI iteration)."""
        raw = os.environ.get("PROMPT_ANYWHERE_MOCK_MODE", "1").strip().lower()
        return raw not in {"0", "false", "off", "no"}

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

        self.mock_mode_action = tray_menu.addAction("Mock Response Mode")
        self.mock_mode_action.setCheckable(True)
        self.mock_mode_action.setChecked(self.mock_response_mode)
        self.mock_mode_action.triggered.connect(self.on_mock_mode_toggled)

        tray_menu.addSeparator()
        
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.app.quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_mock_mode_toggled(self, checked: bool):
        """Enable/disable fake streaming responses for UI testing."""
        self.mock_response_mode = checked
        print(f"Mock response mode set to: {'ON' if checked else 'OFF'}")
    
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

        self.shell_window.set_available_agents(self.core_app.list_supported_agents())
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

        history_prompt = chat.build_prompt_with_history(prompt)
        chat.add_user_message(prompt)
        chat.start_assistant_message()
        self.shell_window.open_drawer(animated=True)
        self.shell_window.set_streaming_state(True)

        should_use_gateway = (
            self.gateway_client is not None
            and not self.mock_response_mode
            and image_bytes is None
            and self.core_app.get_current_agent_name() == "codex"
        )

        if should_use_gateway:
            session_key = chat.session_id or "default"
            self.active_gateway_session_key = session_key
            self.active_gateway_run_id = None
            self.worker = GatewayWorker(
                client=self.gateway_client,
                session_key=session_key,
                prompt=prompt,
                provider="codex-cli",
            )
            self.worker.signals.run_started.connect(self.on_gateway_run_started)
        elif self.mock_response_mode:
            self.worker = MockAgentWorker(prompt, image_bytes)
        else:
            # Get agent from core app
            try:
                agent = self.core_app.get_agent()
            except Exception as e:
                error_text = str(e)
                chat.show_error(error_text)
                QMessageBox.critical(
                    self.shell_window,
                    "Agent Not Available",
                    error_text,
                )
                return
            self.worker = AgentWorker(agent, history_prompt, image_bytes)

        chat = self.shell_window.result_widget
        self.worker.signals.text_chunk.connect(chat.append_text)
        self.worker.signals.finished.connect(chat.set_finished)
        self.worker.signals.finished.connect(self.on_stream_finished)
        self.worker.signals.error.connect(chat.show_error)
        self.worker.signals.error.connect(self.on_stream_finished)
        self.worker.start()

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
    def on_gateway_run_started(self, run_id: str):
        """Track gateway run id for aborts/debug."""
        self.active_gateway_run_id = run_id

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
        try:
            self.core_app.set_default_agent(agent_name)
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
