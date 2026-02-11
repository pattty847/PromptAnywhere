"""Main GUI application coordinator"""
import sys
import signal
from typing import Optional
from threading import Thread
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtCore import Qt, QObject, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap, QCursor

from prompt_anywhere.ui.windows.prompt_window import PromptInputWindow
from prompt_anywhere.ui.windows.main_prompt_window import MainPromptWindow
from prompt_anywhere.ui.windows.result_window import ResultWindow
from prompt_anywhere.ui.windows.history_window import HistoryWindow
from prompt_anywhere.core.app import App
from prompt_anywhere.core.agents.base_agent import BaseAgent
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


class AgentWorker(Thread):
    """Background thread for agent calls"""
    
    def __init__(self, agent: BaseAgent, prompt: str, image_bytes=None):
        super().__init__(daemon=True)
        self.agent = agent
        self.prompt = prompt
        self.image_bytes = image_bytes
        self.signals = StreamSignals()
    
    def run(self):
        """Run agent in background thread"""
        try:
            context = {'image_bytes': self.image_bytes} if self.image_bytes else None
            
            # Stream response from agent
            for chunk in self.agent.send_prompt(self.prompt, context):
                self.signals.text_chunk.emit(chunk)
            
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))


class HotkeySignals(QObject):
    """Signals for hotkey communication"""
    triggered = Signal()


class PromptAnywhereApp:
    """Main application coordinator"""
    
    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Keep running when windows close
        self.prompt_window: Optional[MainPromptWindow] = None
        self.result_window: Optional[ResultWindow] = None
        self.history_window: Optional[HistoryWindow] = None
        self.worker: Optional[AgentWorker] = None

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
        """Display main prompt window"""
        # Close existing prompt window if open
        if self.prompt_window:
            self.prompt_window.close()

        self.prompt_window = MainPromptWindow()
        self.prompt_window.prompt_submitted.connect(self.process_prompt)
        self.prompt_window.feature_triggered.connect(self.handle_feature)

        self.prompt_window.show()
        self.prompt_window.raise_()
        self.prompt_window.activateWindow()
    
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
        if result == "maximize_window" and self.result_window:
            self.result_window.showMaximized()
        elif result == "open_customize":
            print("Opening customize dialog (not implemented yet)")

    @Slot(str, object)
    def process_prompt(self, prompt, image_bytes):
        """Process submitted prompt"""
        print(f"Processing prompt: {prompt[:50]}...")
        self.prompt_window = None

        # Create or reuse result window
        if not self.result_window:
            self.result_window = ResultWindow()
            self.result_window.follow_up_submitted.connect(self.process_prompt)
            self.result_window.session_closed.connect(self.on_result_window_closed)
        self.result_window.ensure_session()

        history_prompt = self.result_window.build_prompt_with_history(prompt)
        self.result_window.add_user_message(prompt)
        self.result_window.start_assistant_message()
        self.result_window.show()

        # Get agent from core app
        agent = self.core_app.get_agent()

        # Start agent worker
        self.worker = AgentWorker(agent, history_prompt, image_bytes)
        self.worker.signals.text_chunk.connect(self.result_window.append_text)
        self.worker.signals.finished.connect(self.result_window.set_finished)
        self.worker.signals.error.connect(self.result_window.show_error)
        self.worker.start()

    def show_history_window(self):
        """Open the history window."""
        if not self.history_window:
            self.history_window = HistoryWindow()
            self.history_window.session_selected.connect(self.open_history_session)
        if self.result_window:
            self.result_window.load_sessions()
            self.history_window.set_sessions(self.result_window.saved_sessions)
        self.history_window.show()

    def open_history_session(self, session_id: str):
        """Open a saved session in the result window."""
        if not self.result_window:
            self.result_window = ResultWindow()
            self.result_window.follow_up_submitted.connect(self.process_prompt)
            self.result_window.session_closed.connect(self.on_result_window_closed)
        self.result_window.load_session(session_id)
        self.result_window.show()

    def on_result_window_closed(self):
        """Refresh history window after session close."""
        if self.history_window and self.result_window:
            self.result_window.load_sessions()
            self.history_window.set_sessions(self.result_window.saved_sessions)
    
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
