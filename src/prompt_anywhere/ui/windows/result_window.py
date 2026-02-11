"""Result window with streaming response"""
import json
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from PySide6.QtWidgets import (
    QWidget, QTextEdit, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QSizePolicy, QStackedLayout
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QCursor, QPixmap, QIcon
from prompt_anywhere.ui.windows.screenshot_overlay import ScreenshotOverlay


class FixedBackgroundLabel(QLabel):
    """Background label that does not affect layout sizing."""

    def sizeHint(self):
        return QSize(0, 0)


class ResultWindow(QWidget):
    """Result UI.

    When `embedded=True`, the widget is meant to be hosted inside another window
    (e.g., PromptShellWindow) and should not set top-level window flags or
    reposition itself.
    """
    follow_up_submitted = Signal(str, object)  # prompt, image_bytes
    session_closed = Signal()
    
    def __init__(self, embedded: bool = False):
        super().__init__()
        self._embedded = embedded
        if not embedded:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setFixedSize(900, 600)
        else:
            # Embedded: let the parent layout drive size.
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.setMinimumHeight(240)
        self.session_id = None
        self.session_conversation = []
        self.saved_sessions = []
        self.active_assistant_index = None
        self.history_path = self.get_history_path()
        
        # Position at cursor (top-level mode only)
        if not self._embedded:
            cursor_pos = QCursor.pos()
            self.move(cursor_pos.x() - 300, cursor_pos.y() - 250)
        
        self.screenshot_bytes = None
        self.screenshot_overlay = None
        self.drag_position = None
        
        self.setup_ui()
        self.load_sessions()
        if not self._embedded:
            self.update_background_pixmap()
    
    def setup_ui(self):
        """Create UI elements"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Container
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)

        self.background_label = FixedBackgroundLabel()
        self.background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.background_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.background_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.background_pixmap = QPixmap(self.get_background_path())

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 15, 15, 140);
                border-radius: 16px;
            }
        """)
        
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(12, 10, 12, 10)
        container_layout.setSpacing(6)
        self.container_layout = container_layout
        
        # Title
        title_layout = QHBoxLayout()
        self.title_layout = title_layout
        title = QLabel("Gemini Response")
        title.setStyleSheet("""
            QLabel {
                color: #FF9D5C;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13pt;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        title_layout.addWidget(title)
        self.loading_label = QLabel("Loading...")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-family: 'Segoe UI', sans-serif;
                font-size: 8pt;
                background: transparent;
                border: none;
                padding-left: 6px;
            }
        """)
        self.loading_label.setVisible(False)
        title_layout.addWidget(self.loading_label)
        title_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("X")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.6);
                border: none;
                font-size: 12pt;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                color: rgba(255, 255, 255, 1.0);
            }
        """)
        close_btn.clicked.connect(self.close)
        self.set_button_icon(close_btn, "close_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg", 12)
        title_layout.addWidget(close_btn)
        
        container_layout.addLayout(title_layout)
        
        # Response display
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setStyleSheet("""
            QTextEdit {
                background-color: rgba(22, 22, 22, 230);
                color: #FFFFFF;
                border: 1px solid rgba(255, 157, 92, 0.3);
                border-radius: 6px;
                padding: 8px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10pt;
            }
            QTextEdit:focus {
                border: 1px solid rgba(255, 157, 92, 0.6);
            }
        """)
        self.text_display.setPlainText("⏳ Loading...")
        container_layout.addWidget(self.text_display, stretch=1)
        
        # Follow-up row (inline input + buttons)
        followup_row = QHBoxLayout()
        followup_row.setContentsMargins(0, 0, 0, 0)
        followup_row.setSpacing(6)

        self.followup_input = QLineEdit()
        self.followup_input.setPlaceholderText("Ask a follow-up question...")
        self.followup_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.followup_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(22, 22, 22, 230);
                color: #FFFFFF;
                border: 1px solid rgba(255, 157, 92, 0.3);
                border-radius: 6px;
                padding: 6px 8px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 9pt;
            }
            QLineEdit:focus {
                border: 1px solid rgba(255, 157, 92, 0.6);
            }
        """)
        self.followup_input.returnPressed.connect(self.submit_followup)
        followup_row.addWidget(self.followup_input)

        self.followup_screenshot_btn = QPushButton("")
        self.followup_screenshot_btn.setFixedSize(30, 26)
        self.followup_screenshot_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 50, 150);
                color: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: rgba(70, 70, 70, 180);
            }
        """)
        self.set_button_icon(self.followup_screenshot_btn, "image_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg", 14)
        self.followup_screenshot_btn.clicked.connect(self.capture_followup_screenshot)
        followup_row.addWidget(self.followup_screenshot_btn)

        self.followup_send_btn = QPushButton("Send")
        self.followup_send_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 157, 92, 220);
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 4px 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 9pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 177, 112, 240);
            }
            QPushButton:pressed {
                background-color: rgba(235, 137, 72, 200);
            }
        """)
        self.set_button_icon(self.followup_send_btn, "send_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg", 14)
        self.followup_send_btn.clicked.connect(self.submit_followup)
        followup_row.addWidget(self.followup_send_btn)

        container_layout.addLayout(followup_row)
        
        self.content_widget.setLayout(container_layout)

        container_stack = QStackedLayout()
        container_stack.setContentsMargins(0, 0, 0, 0)
        container_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        container_stack.addWidget(self.background_label)
        container_stack.addWidget(self.content_widget)
        self.container.setLayout(container_stack)
        layout.addWidget(self.container)
        self.setLayout(layout)
        self.text_display.setText("")
    
    @Slot(str)
    def append_text(self, text):
        """Append streaming text (thread-safe via Qt signal)"""
        self.clear_loading_placeholder()
        
        cursor = self.text_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.text_display.setTextCursor(cursor)
        self.text_display.ensureCursorVisible()
        if self.active_assistant_index is not None:
            self.session_conversation[self.active_assistant_index]["content"] += text
    
    @Slot()
    def set_finished(self):
        """Mark as complete"""
        cursor = self.text_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.text_display.setTextCursor(cursor)
        self.set_loading(False)
        self.save_session()
    
    @Slot(str)
    def show_error(self, error_msg):
        """Display error message"""
        self.append_text(f"\n\n❌ Error: {error_msg}")
        self.set_loading(False)
        self.save_session()
    
    def capture_followup_screenshot(self):
        """Open screenshot overlay for follow-up"""
        self.hide()
        self.screenshot_overlay = ScreenshotOverlay()
        self.screenshot_overlay.screenshot_taken.connect(self.on_followup_screenshot_captured)
        self.screenshot_overlay.show()
    
    @Slot(bytes)
    def on_followup_screenshot_captured(self, image_bytes):
        """Handle captured follow-up screenshot"""
        self.screenshot_bytes = image_bytes
        self.followup_screenshot_label.setText("✓ Screenshot")
        self.screenshot_overlay = None
        self.show()
        self.followup_input.setFocus()
    
    def submit_followup(self):
        """Submit follow-up question"""
        prompt = self.followup_input.text().strip()
        if not prompt:
            return
        
        self.follow_up_submitted.emit(prompt, self.screenshot_bytes)
        # Clear input and screenshot
        self.followup_input.clear()
        self.screenshot_bytes = None
        self.followup_screenshot_label.clear()

    def add_user_message(self, prompt: str):
        """Append a user message to the display and history."""
        self.ensure_session()
        self.clear_loading_placeholder()
        self.append_block(f"You: {prompt}")
        self.session_conversation.append({"role": "user", "content": prompt})
        self.save_session()

    def start_assistant_message(self):
        """Start a new assistant response in the display and history."""
        self.ensure_session()
        self.clear_loading_placeholder()
        self.append_block("Assistant:")
        self.session_conversation.append({"role": "assistant", "content": ""})
        self.active_assistant_index = len(self.session_conversation) - 1
        self.set_loading(True)

    def build_prompt_with_history(self, new_prompt: str) -> str:
        """Build a prompt including conversation history for context."""
        if not self.session_conversation:
            return new_prompt
        lines = []
        for entry in self.session_conversation:
            role = "User" if entry["role"] == "user" else "Assistant"
            lines.append(f"{role}: {entry['content']}")
        lines.append(f"User: {new_prompt}")
        lines.append("Assistant:")
        return "\n".join(lines)

    def get_history_path(self) -> Path:
        """Return path to the persistent chat sessions file."""
        base_dir = Path.home() / ".prompt_anywhere"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / "chat_sessions.json"

    def get_asset_path(self, filename: str) -> str:
        """Return the full path to an asset file."""
        return str(Path(__file__).resolve().parents[1] / "assets" / filename)

    def get_background_path(self) -> str:
        """Return the background image path."""
        return self.get_asset_path("background.png")

    def set_button_icon(self, button: QPushButton, filename: str, size: int):
        """Apply an icon from assets to a button."""
        path = self.get_asset_path(filename)
        icon = QIcon(path)
        if icon.isNull():
            return
        button.setIcon(icon)
        button.setIconSize(QSize(size, size))

    def update_background_pixmap(self):
        """Scale and apply the background image to the container."""
        if self.background_pixmap.isNull():
            return
        target_size = self.container.size()
        source = self.background_pixmap
        if source.width() < target_size.width() or source.height() < target_size.height():
            source = source.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
        x = max(0, (source.width() - target_size.width()) // 2)
        y = max(0, (source.height() - target_size.height()) // 2)
        cropped = source.copy(x, y, target_size.width(), target_size.height())
        self.background_label.setPixmap(cropped)
        self.background_label.resize(target_size)

    def load_sessions(self):
        """Load session history from disk for history view."""
        if not self.history_path.exists():
            return
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("sessions"), list):
                self.saved_sessions = data.get("sessions", [])
        except (json.JSONDecodeError, OSError):
            return

    def save_session(self):
        """Persist the current session to disk."""
        if not self.session_id:
            return
        sessions = []
        if self.history_path.exists():
            try:
                data = json.loads(self.history_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("sessions"), list):
                    sessions = data.get("sessions", [])
            except (json.JSONDecodeError, OSError):
                sessions = []
        now = datetime.now().isoformat(timespec="seconds")
        session_payload = {
            "id": self.session_id,
            "created_at": self.session_created_at,
            "updated_at": now,
            "messages": self.session_conversation,
        }
        updated = False
        for index, session in enumerate(sessions):
            if session.get("id") == self.session_id:
                sessions[index] = session_payload
                updated = True
                break
        if not updated:
            sessions.append(session_payload)
        try:
            self.history_path.write_text(
                json.dumps({"sessions": sessions}, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except OSError:
            return

    def render_conversation(self, entries=None):
        """Render the selected conversation history in the display."""
        self.text_display.setText("")
        self.active_assistant_index = None
        entries = entries if entries is not None else self.session_conversation
        for entry in entries:
            role = "You" if entry["role"] == "user" else "Assistant"
            self.append_block(f"{role}: {entry['content']}")

    def show_history(self):
        """Show the window with the current conversation history."""
        if self.session_id:
            self.render_conversation(self.session_conversation)
        self.show()
        self.show()

    def set_loading(self, is_loading: bool):
        """Toggle loading indicator."""
        if hasattr(self, "loading_label"):
            self.loading_label.setVisible(is_loading)

    def resizeEvent(self, event):
        """Keep background image in sync with window size."""
        super().resizeEvent(event)
        if not self._embedded:
            self.update_background_pixmap()

    def closeEvent(self, event):
        """Mark session end on close."""
        self.save_session()
        self.session_id = None
        self.session_conversation = []
        self.active_assistant_index = None
        self.session_closed.emit()
        super().closeEvent(event)

    def ensure_session(self):
        """Ensure there is an active session."""
        if self.session_id:
            return
        self.session_id = self.generate_session_id()
        self.session_created_at = datetime.now().isoformat(timespec="seconds")
        self.session_conversation = []

    def generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"

    def load_session(self, session_id: str):
        """Load a saved session by ID into the window."""
        self.load_sessions()
        for session in self.saved_sessions:
            if session.get("id") == session_id:
                self.session_id = session_id
                self.session_created_at = session.get("created_at")
                self.session_conversation = session.get("messages", [])
                self.render_conversation(self.session_conversation)
                return

    def clear_loading_placeholder(self):
        """Clear any loading placeholder text."""
        if self.text_display.toPlainText().strip() in ("⏳ Loading...", "Loading..."):
            self.text_display.clear()

    def append_block(self, text: str):
        """Append a block of text separated by blank lines."""
        cursor = self.text_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        if self.text_display.toPlainText().strip():
            cursor.insertText("\n\n")
        cursor.insertText(text + "\n")
        self.text_display.setTextCursor(cursor)

    
    def mousePressEvent(self, event):
        """Enable window dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        """Handle window dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
    
    def keyPressEvent(self, event):
        """ESC or Q to close"""
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            self.close()
