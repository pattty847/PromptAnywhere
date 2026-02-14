"""Result window with streaming response displayed as chat bubbles."""

from datetime import datetime
from uuid import uuid4

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from prompt_anywhere.ui.common import (
    FixedBackgroundLabel,
    get_asset_path,
    set_button_icon,
    update_background_pixmap as common_update_background_pixmap,
)
from prompt_anywhere.ui.services.session_manager import (
    get_history_path as get_session_history_path,
    load_session_by_id,
    load_sessions as load_sessions_from_disk,
    save_session as save_session_to_disk,
)
from prompt_anywhere.ui.widgets.chat_bubble import ChatBubble
from prompt_anywhere.ui.windows.screenshot_overlay import ScreenshotOverlay
from prompt_anywhere.ui.windows.result_window_actions import copy_to_clipboard, update_code_block_bar


class ResultWindow(QWidget):
    """Result UI using per-message chat bubbles.

    When ``embedded=True``, the widget is meant to be hosted inside another
    window (e.g., PromptShellWindow) and should not set top-level window
    flags or reposition itself.
    """

    follow_up_submitted = Signal(str, object)  # prompt, image_bytes
    session_closed = Signal()

    def __init__(
        self,
        embedded: bool = False,
        show_chrome: bool = True,
        show_followup_input: bool = True,
    ):
        super().__init__()
        self._embedded = embedded
        self._show_chrome = show_chrome
        self._show_followup_input = show_followup_input

        if not embedded:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setFixedSize(900, 600)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.setMinimumHeight(200)

        self.session_id = None
        self.session_created_at = None
        self.session_conversation: list[dict] = []
        self.saved_sessions: list[dict] = []
        self.active_assistant_index: int | None = None
        self.history_path = get_session_history_path()

        if not self._embedded:
            cursor_pos = QCursor.pos()
            self.move(cursor_pos.x() - 300, cursor_pos.y() - 250)

        self.screenshot_bytes = None
        self.screenshot_overlay = None
        self.drag_position = None

        # Chat bubble tracking
        self._bubbles: list[ChatBubble] = []
        self._active_bubble: ChatBubble | None = None

        self.setup_ui()

    # -- Setup ----------------------------------------------------------------

    def setup_ui(self):
        """Create UI elements."""
        self._build_container()
        self._build_header()
        self._build_main_content()
        self._wire_signals()
        self._apply_initial_state()

    def _build_container(self):
        """Create root layout, container, background, and content widget skeleton."""
        self._root_layout = QVBoxLayout()
        self._root_layout.setContentsMargins(0, 0, 0, 0)

        if self._show_chrome:
            self.container = QWidget()
            self.container.setStyleSheet(
                """
                QWidget {
                    background-color: transparent;
                    border-radius: 16px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }
                """
            )

            self.background_label = FixedBackgroundLabel()
            self.background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.background_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            self.background_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.background_pixmap = QPixmap(self.get_background_path())

            self.content_widget = QWidget()
            self.content_widget.setStyleSheet(
                """
                QWidget {
                    background-color: rgba(15, 15, 15, 140);
                    border-radius: 16px;
                }
                """
            )
        else:
            self.container = self
            self.background_pixmap = QPixmap()
            self.content_widget = QWidget()
            self.content_widget.setStyleSheet("QWidget { background: transparent; border: none; }")

        self._container_layout = QVBoxLayout()
        if self._show_chrome:
            self._container_layout.setContentsMargins(12, 10, 12, 10)
        else:
            self._container_layout.setContentsMargins(5, 2, 5, 2)
        self._container_layout.setSpacing(4)

        self.loading_label = QLabel("Loading...")
        self.loading_label.setStyleSheet(
            """
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-family: 'Segoe UI', sans-serif;
                font-size: 8pt;
                background: transparent;
                border: none;
                padding-left: 6px;
            }
            """
        )
        self.loading_label.setVisible(False)

    def _build_header(self):
        """Build title row with close button (chrome mode only)."""
        if not self._show_chrome:
            return
        title_layout = QHBoxLayout()
        title = QLabel("Gemini Response")
        title.setStyleSheet(
            """
            QLabel {
                color: #FF9D5C;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13pt;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 0px;
            }
            """
        )
        title_layout.addWidget(title)
        title_layout.addWidget(self.loading_label)
        title_layout.addStretch()

        self.close_btn = QPushButton("X")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setStyleSheet(
            """
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
            """
        )
        set_button_icon(self.close_btn, "close_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg", 12)
        title_layout.addWidget(self.close_btn)
        self._container_layout.addLayout(title_layout)

    def _build_main_content(self):
        """Build chat scroll area, code blocks bar, and optional follow-up input."""
        # -- Scroll area with chat bubbles ------------------------------------
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chat_scroll.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(30, 30, 30, 80);
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.18);
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.30);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )

        self._chat_container = QWidget()
        self._chat_container.setStyleSheet("QWidget { background: transparent; border: none; }")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(0, 0, 0, 0)
        self._chat_layout.setSpacing(6)
        self._chat_layout.addStretch()

        self._chat_scroll.setWidget(self._chat_container)
        self._container_layout.addWidget(self._chat_scroll, stretch=1)

        # -- Code blocks bar --------------------------------------------------
        self.code_blocks_bar = QWidget()
        self.code_blocks_bar.setVisible(False)
        self.code_blocks_layout = QHBoxLayout()
        self.code_blocks_layout.setContentsMargins(0, 0, 0, 0)
        self.code_blocks_layout.setSpacing(6)
        self.code_blocks_bar.setLayout(self.code_blocks_layout)
        self._container_layout.addWidget(self.code_blocks_bar)

        self._last_code_blocks: list[str] = []

        # -- Follow-up input --------------------------------------------------
        if self._show_followup_input:
            followup_row = QHBoxLayout()
            followup_row.setContentsMargins(0, 0, 0, 0)
            followup_row.setSpacing(6)

            self.followup_input = QLineEdit()
            self.followup_input.setPlaceholderText("Ask a follow-up question...")
            self.followup_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.followup_input.setStyleSheet(
                """
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
                """
            )
            followup_row.addWidget(self.followup_input)

            self.followup_screenshot_btn = QPushButton("")
            self.followup_screenshot_btn.setFixedSize(30, 26)
            self.followup_screenshot_btn.setStyleSheet(
                """
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
                """
            )
            set_button_icon(
                self.followup_screenshot_btn,
                "image_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
                14,
            )
            followup_row.addWidget(self.followup_screenshot_btn)

            self.followup_send_btn = QPushButton("Send")
            self.followup_send_btn.setStyleSheet(
                """
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
                """
            )
            set_button_icon(self.followup_send_btn, "send_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg", 14)
            followup_row.addWidget(self.followup_send_btn)
            self._container_layout.addLayout(followup_row)

        self.content_widget.setLayout(self._container_layout)

        if self._show_chrome:
            container_stack = QStackedLayout()
            container_stack.setContentsMargins(0, 0, 0, 0)
            container_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
            container_stack.addWidget(self.background_label)
            container_stack.addWidget(self.content_widget)
            self.container.setLayout(container_stack)
            self._root_layout.addWidget(self.container)
        else:
            self._root_layout.addWidget(self.content_widget)
        self.setLayout(self._root_layout)

    def _wire_signals(self):
        """Connect widget signals to slots."""
        if self._show_chrome:
            self.close_btn.clicked.connect(self.close)
        if self._show_followup_input:
            self.followup_input.returnPressed.connect(self.submit_followup)
            self.followup_screenshot_btn.clicked.connect(self.capture_followup_screenshot)
            self.followup_send_btn.clicked.connect(self.submit_followup)

    def _apply_initial_state(self):
        """Load sessions, update background."""
        self.load_sessions()
        if not self._embedded and self._show_chrome:
            self.update_background_pixmap()

    # -- Bubble management ----------------------------------------------------

    def _add_bubble(self, role: str, content: str = "") -> ChatBubble:
        """Create a new chat bubble and add it to the scroll area."""
        bubble = ChatBubble(role=role, content=content)
        self._bubbles.append(bubble)
        # Insert before the trailing stretch
        idx = self._chat_layout.count() - 1
        self._chat_layout.insertWidget(idx, bubble)
        return bubble

    def _clear_bubbles(self) -> None:
        """Remove all chat bubbles."""
        for bubble in self._bubbles:
            self._chat_layout.removeWidget(bubble)
            bubble.deleteLater()
        self._bubbles.clear()
        self._active_bubble = None

    def _scroll_to_bottom(self) -> None:
        """Scroll the chat area to the bottom."""
        vbar = self._chat_scroll.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def _is_scrolled_to_bottom(self) -> bool:
        vbar = self._chat_scroll.verticalScrollBar()
        return (vbar.maximum() - vbar.value()) <= 20

    # -- Public message API ---------------------------------------------------

    @Slot(str)
    def append_text(self, text: str) -> None:
        """Append streaming text to the active assistant bubble.

        Autoscroll policy: only stick to bottom if user is already near bottom.
        """
        if self._active_bubble is None:
            return

        was_at_bottom = self._is_scrolled_to_bottom()
        self._active_bubble.append_content(text)

        if was_at_bottom:
            self._scroll_to_bottom()

        if self.active_assistant_index is not None:
            self.session_conversation[self.active_assistant_index]["content"] += text

    @Slot()
    def set_finished(self) -> None:
        """Mark the current response as complete."""
        if self.active_assistant_index is not None:
            self._refresh_code_block_buttons(
                self.session_conversation[self.active_assistant_index]["content"]
            )
        self._active_bubble = None
        self.set_loading(False)
        self.save_session()

    @Slot(str)
    def show_error(self, error_msg: str) -> None:
        """Display error in the active bubble or as a new message."""
        if self._active_bubble:
            self._active_bubble.append_content(f"\n\nError: {error_msg}")
        else:
            self._add_bubble("assistant", f"Error: {error_msg}")
        self.set_loading(False)
        self.save_session()
        self._scroll_to_bottom()

    def add_user_message(self, prompt: str) -> None:
        """Append a user message bubble and record in history."""
        self.ensure_session()
        self._add_bubble("user", prompt)
        self.session_conversation.append({"role": "user", "content": prompt})
        self.save_session()
        self._scroll_to_bottom()

    def start_assistant_message(self) -> None:
        """Start a new empty assistant bubble for streaming."""
        self.ensure_session()
        bubble = self._add_bubble("assistant")
        self._active_bubble = bubble
        self.session_conversation.append({"role": "assistant", "content": ""})
        self.active_assistant_index = len(self.session_conversation) - 1
        self.set_loading(True)
        self._refresh_code_block_buttons("")
        self._scroll_to_bottom()

    def render_conversation(self, entries=None) -> None:
        """Render a full conversation as bubbles."""
        self._clear_bubbles()
        self.active_assistant_index = None
        entries = entries if entries is not None else self.session_conversation
        for entry in entries:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            self._add_bubble(role, content)
        self._scroll_to_bottom()

    def copy_last_assistant_message(self) -> None:
        """Copy the most recent assistant message to clipboard."""
        last = ""
        for entry in reversed(self.session_conversation):
            if entry.get("role") == "assistant":
                last = entry.get("content") or ""
                break
        copy_to_clipboard(last)

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

    # -- Code blocks ----------------------------------------------------------

    def _refresh_code_block_buttons(self, assistant_text: str) -> None:
        """Rebuild code-block copy buttons for the latest assistant message."""
        self._last_code_blocks = update_code_block_bar(
            self.code_blocks_bar,
            self.code_blocks_layout,
            assistant_text,
            on_copy=copy_to_clipboard,
        )

    # -- Follow-up ------------------------------------------------------------

    def capture_followup_screenshot(self) -> None:
        """Open screenshot overlay for follow-up."""
        if not hasattr(self, "followup_input"):
            return
        window_to_hide = self.window() if self._embedded else self
        window_to_hide.hide()
        self.screenshot_overlay = ScreenshotOverlay()
        self.screenshot_overlay.screenshot_taken.connect(self.on_followup_screenshot_captured)
        self.screenshot_overlay.show()

    @Slot(bytes)
    def on_followup_screenshot_captured(self, image_bytes: bytes) -> None:
        """Handle captured follow-up screenshot."""
        self.screenshot_bytes = image_bytes
        self.screenshot_overlay = None
        window_to_show = self.window() if self._embedded else self
        window_to_show.show()
        if hasattr(self, "followup_input"):
            self.followup_input.setFocus()

    def submit_followup(self) -> None:
        """Submit follow-up question."""
        if not hasattr(self, "followup_input"):
            return
        prompt = self.followup_input.text().strip()
        if not prompt:
            return
        self.follow_up_submitted.emit(prompt, self.screenshot_bytes)
        self.followup_input.clear()
        self.screenshot_bytes = None

    # -- Session management ---------------------------------------------------

    def ensure_session(self) -> None:
        """Ensure there is an active session."""
        if self.session_id:
            return
        self.session_id = self.generate_session_id()
        self.session_created_at = datetime.now().isoformat(timespec="seconds")
        self.session_conversation = []

    def generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"

    def load_sessions(self) -> None:
        """Load session history from disk for history view."""
        self.saved_sessions = load_sessions_from_disk(self.history_path)

    def save_session(self) -> None:
        """Persist the current session to disk."""
        if not self.session_id:
            return
        now = datetime.now().isoformat(timespec="seconds")
        session_payload = {
            "id": self.session_id,
            "created_at": self.session_created_at,
            "updated_at": now,
            "messages": self.session_conversation,
        }
        save_session_to_disk(self.history_path, session_payload)

    def load_session(self, session_id: str) -> None:
        """Load a saved session by ID into the window."""
        self.load_sessions()
        session = load_session_by_id(self.history_path, session_id)
        if session is not None:
            self.session_id = session_id
            self.session_created_at = session.get("created_at")
            self.session_conversation = session.get("messages", [])
            self.render_conversation(self.session_conversation)

    def show_history(self) -> None:
        """Show the window with the current conversation history."""
        if self.session_id:
            self.render_conversation(self.session_conversation)
        self.show()

    # -- Loading / background -------------------------------------------------

    def set_loading(self, is_loading: bool) -> None:
        """Toggle loading indicator."""
        if hasattr(self, "loading_label"):
            self.loading_label.setVisible(is_loading)

    def get_background_path(self) -> str:
        """Return the background image path."""
        return get_asset_path("background.png")

    def update_background_pixmap(self) -> None:
        """Scale and apply the background image to the container."""
        if not self._show_chrome:
            return
        common_update_background_pixmap(
            self.background_label, self.background_pixmap, self.container.size()
        )

    def resizeEvent(self, event) -> None:
        """Keep background image in sync with window size."""
        super().resizeEvent(event)
        if not self._embedded and self._show_chrome:
            self.update_background_pixmap()

    # -- Window events --------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Mark session end on close."""
        self.save_session()
        self.session_id = None
        self.session_conversation = []
        self.active_assistant_index = None
        self._clear_bubbles()
        self.session_closed.emit()
        super().closeEvent(event)

    def mousePressEvent(self, event) -> None:
        """Enable window dragging (top-level only)."""
        if self._embedded:
            return super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        """Handle window dragging (top-level only)."""
        if self._embedded:
            return super().mouseMoveEvent(event)
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)

    def keyPressEvent(self, event) -> None:
        """ESC or Q to close in top-level mode only."""
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            if self._embedded:
                event.ignore()
                return
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)
