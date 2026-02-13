"""Single-window shell with a chat drawer.

This keeps PromptAnywhere in one floating surface:
- top: shell header (title + close)
- middle: collapsible chat drawer (ResultWindow in embedded content mode)
- bottom: prompt panel (MainPromptWindow in embedded content mode)

Drawer animation uses direct window-geometry manipulation so the prompt
panel stays perfectly still.  Edge-drag resize handles let the user
enlarge the window freely.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QRect, Qt, Signal, QSize, QVariantAnimation
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from prompt_anywhere.ui.common import (
    FixedBackgroundLabel,
    apply_rounded_mask,
    get_asset_path,
    set_button_icon,
    update_background_pixmap as common_update_background_pixmap,
)
from prompt_anywhere.ui.windows.main_prompt_window import MainPromptWindow
from prompt_anywhere.ui.windows.result_window import ResultWindow


# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

_RESIZE_GRIP = 8       # px from each edge that counts as a resize handle
_MIN_WIDTH = 420
_MIN_HEIGHT = 180
_ANIM_DURATION_MS = 200

_EDGE_CURSORS = {
    "top": Qt.CursorShape.SizeVerCursor,
    "bottom": Qt.CursorShape.SizeVerCursor,
    "left": Qt.CursorShape.SizeHorCursor,
    "right": Qt.CursorShape.SizeHorCursor,
    "top-left": Qt.CursorShape.SizeFDiagCursor,
    "bottom-right": Qt.CursorShape.SizeFDiagCursor,
    "top-right": Qt.CursorShape.SizeBDiagCursor,
    "bottom-left": Qt.CursorShape.SizeBDiagCursor,
}


class PromptShellWindow(QWidget):
    """Main always-on-top window containing prompt + drawer."""

    prompt_submitted = Signal(str, object)  # prompt, image_bytes
    feature_triggered = Signal(str, str)  # feature_name, prompt
    follow_up_submitted = Signal(str, object)  # prompt, image_bytes
    session_closed = Signal()
    history_session_selected = Signal(str)
    agent_selected = Signal(str)
    stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drawer_open = False
        self._drawer_anim: QVariantAnimation | None = None
        self._drawer_open_height = 380
        self._bottom_anchor: int | None = None
        self._history_return_target = "collapsed"

        # Resize-handle state
        self._resize_edge: str | None = None
        self._resize_start_global = None
        self._resize_start_geo: QRect | None = None
        self._drag_pos = None

        # Debug
        self._ui_debug_enabled = self._is_debug_enabled()
        self._last_anim_debug_ts = 0.0

        self.setup_ui()

    # ── Setup ────────────────────────────────────────────────────────────

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
        self._root_layout.setSpacing(0)

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

        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(5, 5, 5, 5)
        self._content_layout.setSpacing(0)

    def _build_header(self):
        """Build shell header row with title and close button."""
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 4)
        header_layout.setSpacing(0)

        self.title_label = QLabel("Prompt Anywhere")
        self.title_label.setStyleSheet(
            """
            QLabel {
                color: #FF9D5C;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12pt;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 0px;
            }
            """
        )
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.close_btn = QPushButton("")
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
        header_layout.addWidget(self.close_btn)

        self._content_layout.addLayout(header_layout)

    def _build_main_content(self):
        """Build drawer and prompt panel, assemble layout."""
        # -- Drawer frame (stretch=1: absorbs all extra height) ---------------
        self.drawer_frame = QFrame()
        self.drawer_frame.setObjectName("chatDrawer")
        self.drawer_frame.setStyleSheet("QFrame#chatDrawer { background: transparent; border: none; }")
        self.drawer_layout = QVBoxLayout()
        self.drawer_layout.setContentsMargins(0, 0, 0, 4)
        self.drawer_layout.setSpacing(0)
        self.drawer_frame.setLayout(self.drawer_layout)
        self.drawer_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.drawer_frame.setMinimumHeight(0)

        self.drawer_stack = QStackedWidget()
        self.drawer_stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

        self.result_widget = ResultWindow(
            embedded=True,
            show_chrome=False,
            show_followup_input=False,
        )
        self.drawer_stack.addWidget(self.result_widget)

        self.history_widget = self._build_history_widget()
        self.drawer_stack.addWidget(self.history_widget)
        self.drawer_layout.addWidget(self.drawer_stack)

        # Start hidden — no height consumed
        self.drawer_frame.setVisible(False)

        # -- Prompt panel (stretch=0: keeps its natural size) -----------------
        self.prompt_widget = MainPromptWindow(embedded=True, show_chrome=False)
        self.prompt_widget.setObjectName("promptPanel")
        self.result_widget.setObjectName("chatPanel")
        self.drawer_frame.setObjectName("drawerFrame")
        self.drawer_stack.setObjectName("drawerStack")

        self._content_layout.addWidget(self.drawer_frame, stretch=1)
        self._content_layout.addWidget(self.prompt_widget, stretch=0)

        self.content_widget.setLayout(self._content_layout)

        container_stack = QStackedLayout()
        container_stack.setContentsMargins(0, 0, 0, 0)
        container_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        container_stack.addWidget(self.background_label)
        container_stack.addWidget(self.content_widget)
        self.container.setLayout(container_stack)

        self._root_layout.addWidget(self.container)
        self.setLayout(self._root_layout)

    def _wire_signals(self):
        """Connect widget signals to slots."""
        self.close_btn.clicked.connect(self.hide)
        self.prompt_widget.prompt_submitted.connect(self._on_prompt_submitted)
        self.prompt_widget.feature_triggered.connect(self.feature_triggered)
        self.prompt_widget.agent_selected.connect(self.agent_selected)
        self.prompt_widget.stop_requested.connect(self.stop_requested)
        self.result_widget.follow_up_submitted.connect(self.follow_up_submitted)
        self.result_widget.session_closed.connect(self.session_closed)

    def _apply_initial_state(self):
        """Set size, mask, background, and debug state."""
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)
        self.resize(self.prompt_widget.window_width, self.prompt_widget.window_height + 24)
        self.adjustSize()
        self.update_window_mask()
        self.update_background_pixmap()
        self._setup_ui_debugging()

    # ── Debug helpers ────────────────────────────────────────────────────

    def _is_debug_enabled(self) -> bool:
        raw = os.environ.get("PROMPT_ANYWHERE_UI_DEBUG", "0").strip().lower()
        return raw in {"1", "true", "on", "yes"}

    def _setup_ui_debugging(self) -> None:
        if not self._ui_debug_enabled:
            return
        print("[UI_DEBUG] PromptShellWindow debug mode enabled.")

    def _debug(self, message: str) -> None:
        if self._ui_debug_enabled:
            print(f"[UI_DEBUG] {message}")

    # ── Background / mask ────────────────────────────────────────────────

    def get_background_path(self) -> str:
        return get_asset_path("background.png")

    def update_background_pixmap(self) -> None:
        common_update_background_pixmap(
            self.background_label, self.background_pixmap, self.container.size()
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_window_mask()
        self.update_background_pixmap()

    def update_window_mask(self) -> None:
        apply_rounded_mask(self, radius=16)

    # ── Prompt submission ────────────────────────────────────────────────

    def _on_prompt_submitted(self, prompt: str, image_bytes: object) -> None:
        self.open_drawer(animated=True)
        self.prompt_submitted.emit(prompt, image_bytes)

    # ── Drawer open / close (geometry-based) ─────────────────────────────

    def is_drawer_open(self) -> bool:
        return self._drawer_open

    def toggle_drawer(self, animated: bool = True) -> None:
        if self._drawer_open:
            self.close_drawer(animated=animated)
        else:
            self.open_drawer(animated=animated)

    def open_drawer(self, animated: bool = True) -> None:
        """Open the chat drawer by expanding the window upward."""
        if self._drawer_open:
            return
        self._drawer_open = True

        # Anchor bottom edge
        self._bottom_anchor = self.y() + self.height()
        collapsed_h = self.height()
        expanded_h = collapsed_h + self._drawer_open_height

        # Make drawer visible (it will get space as window grows)
        self.drawer_frame.setVisible(True)

        self._debug(
            f"open_drawer: collapsed={collapsed_h} expanded={expanded_h} "
            f"anchor={self._bottom_anchor}"
        )

        if not animated:
            self.setGeometry(
                self.x(),
                self._bottom_anchor - expanded_h,
                self.width(),
                expanded_h,
            )
            self._bottom_anchor = None
            return

        self._start_height_anim(collapsed_h, expanded_h)

    def close_drawer(self, animated: bool = True) -> None:
        """Close the chat drawer by shrinking the window downward."""
        if not self._drawer_open:
            return
        self._drawer_open = False

        self._bottom_anchor = self.y() + self.height()
        expanded_h = self.height()
        collapsed_h = max(_MIN_HEIGHT, expanded_h - self._drawer_open_height)

        self._debug(
            f"close_drawer: expanded={expanded_h} collapsed={collapsed_h} "
            f"anchor={self._bottom_anchor}"
        )

        if not animated:
            self.drawer_frame.setVisible(False)
            self.setGeometry(
                self.x(),
                self._bottom_anchor - collapsed_h,
                self.width(),
                collapsed_h,
            )
            self._bottom_anchor = None
            return

        self._start_height_anim(expanded_h, collapsed_h, hide_drawer_on_done=True)

    def _start_height_anim(
        self,
        start_h: int,
        end_h: int,
        hide_drawer_on_done: bool = False,
    ) -> None:
        """Animate window height between two values, keeping bottom edge fixed."""
        if self._drawer_anim is not None:
            self._drawer_anim.stop()
            self._drawer_anim = None

        anim = QVariantAnimation()
        anim.setDuration(_ANIM_DURATION_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(start_h)
        anim.setEndValue(end_h)
        anim.valueChanged.connect(self._on_height_anim_tick)

        def on_finished() -> None:
            if hide_drawer_on_done:
                self.drawer_frame.setVisible(False)
            self._bottom_anchor = None
            self._drawer_anim = None

        anim.finished.connect(on_finished)
        self._drawer_anim = anim
        anim.start()

    def _on_height_anim_tick(self, value) -> None:
        """Single setGeometry per frame — no layout manipulation."""
        h = int(value)
        if self._bottom_anchor is not None:
            self.setGeometry(self.x(), self._bottom_anchor - h, self.width(), h)

    # ── Resize handles ───────────────────────────────────────────────────

    @staticmethod
    def _get_resize_edge(pos, rect_size) -> str | None:
        """Detect which edge/corner the mouse is on (or None)."""
        grip = _RESIZE_GRIP
        x, y = pos.x(), pos.y()
        w, h = rect_size.width(), rect_size.height()

        on_top = y <= grip
        on_bottom = y >= h - grip
        on_left = x <= grip
        on_right = x >= w - grip

        if on_top and on_left:
            return "top-left"
        if on_top and on_right:
            return "top-right"
        if on_bottom and on_left:
            return "bottom-left"
        if on_bottom and on_right:
            return "bottom-right"
        if on_top:
            return "top"
        if on_bottom:
            return "bottom"
        if on_left:
            return "left"
        if on_right:
            return "right"
        return None

    def _apply_resize(self, global_pos) -> None:
        """Update geometry while user drags a resize handle."""
        if self._resize_edge is None or self._resize_start_geo is None:
            return

        dx = global_pos.x() - self._resize_start_global.x()
        dy = global_pos.y() - self._resize_start_global.y()
        geo = QRect(self._resize_start_geo)
        edge = self._resize_edge

        if "right" in edge:
            geo.setRight(self._resize_start_geo.right() + dx)
        if "left" in edge:
            geo.setLeft(self._resize_start_geo.left() + dx)
        if "bottom" in edge:
            geo.setBottom(self._resize_start_geo.bottom() + dy)
        if "top" in edge:
            geo.setTop(self._resize_start_geo.top() + dy)

        # Enforce minimum size
        if geo.width() < _MIN_WIDTH:
            if "left" in edge:
                geo.setLeft(geo.right() - _MIN_WIDTH)
            else:
                geo.setRight(geo.left() + _MIN_WIDTH)
        if geo.height() < _MIN_HEIGHT:
            if "top" in edge:
                geo.setTop(geo.bottom() - _MIN_HEIGHT)
            else:
                geo.setBottom(geo.top() + _MIN_HEIGHT)

        self.setGeometry(geo)

        # If the user dragged tall enough to show the drawer, auto-open it
        prompt_h = self.prompt_widget.sizeHint().height()
        available_for_drawer = self.height() - prompt_h - 34  # header + margins
        if not self._drawer_open and available_for_drawer > 40:
            self._drawer_open = True
            self.drawer_frame.setVisible(True)

    # ── Mouse events (drag + resize) ─────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        edge = self._get_resize_edge(event.position().toPoint(), self.size())
        if edge:
            # Start resize
            self._resize_edge = edge
            self._resize_start_global = event.globalPosition().toPoint()
            self._resize_start_geo = QRect(self.geometry())
            event.accept()
            return

        # Start drag
        self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event):
        # Active resize
        if self._resize_edge is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self._apply_resize(event.globalPosition().toPoint())
            event.accept()
            return

        # Active drag
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return

        # Hover: update cursor for resize handles
        if event.buttons() == Qt.MouseButton.NoButton:
            edge = self._get_resize_edge(event.position().toPoint(), self.size())
            if edge:
                self.setCursor(_EDGE_CURSORS[edge])
            else:
                self.unsetCursor()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resize_edge is not None:
            self._resize_edge = None
            self._resize_start_global = None
            self._resize_start_geo = None
            event.accept()
            return
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ── Forwarded widget API ─────────────────────────────────────────────

    def focus_input(self) -> None:
        self.prompt_widget.input_field.setFocus()

    def set_available_agents(self, agent_names: list[str]) -> None:
        self.prompt_widget.set_available_agents(agent_names)

    def set_selected_agent(self, agent_name: str) -> None:
        self.prompt_widget.set_selected_agent(agent_name)

    def set_streaming_state(self, active: bool) -> None:
        self.prompt_widget.set_streaming_state(active)

    # ── History panel ────────────────────────────────────────────────────

    def _build_history_widget(self) -> QWidget:
        """Create in-drawer history panel."""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(7, 5, 0, 0)
        header.setSpacing(6)

        back_btn = QPushButton("Back")
        back_btn.setFixedHeight(24)
        back_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(50, 50, 50, 150);
                color: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                font-size: 8pt;
                padding: 2px 10px;
            }
            QPushButton:hover {
                background-color: rgba(70, 70, 70, 180);
            }
            """
        )
        back_btn.clicked.connect(lambda _checked=False: self.exit_history_mode(animated=True))
        header.addWidget(back_btn)

        title = QLabel("History")
        title.setStyleSheet(
            """
            QLabel {
                color: #FF9D5C;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11pt;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            """
        )
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        self.history_list = QListWidget()
        self.history_list.setWordWrap(True)
        self.history_list.setUniformItemSizes(False)
        self.history_list.setStyleSheet(
            """
            QListWidget {
                background-color: rgba(22, 22, 22, 230);
                color: #FFFFFF;
                border: 1px solid rgba(255, 157, 92, 0.3);
                border-radius: 6px;
                padding: 6px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 9pt;
            }
            QListWidget::item {
                padding: 6px 4px;
            }
            QListWidget::item:selected {
                background-color: rgba(255, 157, 92, 0.2);
                border-radius: 4px;
            }
            """
        )
        self.history_list.itemClicked.connect(self._on_history_item_clicked)
        layout.addWidget(self.history_list, stretch=1)

        panel.setLayout(layout)
        return panel

    def set_history_sessions(self, sessions: list[dict]) -> None:
        self.history_list.clear()
        sorted_sessions = sorted(
            sessions,
            key=lambda s: self._session_sort_key(s),
            reverse=True,
        )
        for session in sorted_sessions:
            msg_count = len(session.get("messages", []))
            ts_raw = session.get("updated_at") or session.get("created_at") or ""
            timestamp = self._format_session_timestamp(ts_raw)
            preview = self._session_preview(session)
            label = f"{timestamp}  ({msg_count} messages)\n{preview}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, session.get("id"))
            self.history_list.addItem(item)

    def _session_sort_key(self, session: dict) -> datetime:
        ts_raw = session.get("updated_at") or session.get("created_at") or ""
        parsed = self._parse_session_datetime(ts_raw)
        return parsed if parsed is not None else datetime.min

    def _parse_session_datetime(self, raw_value: str) -> datetime | None:
        if not raw_value:
            return None
        try:
            return datetime.fromisoformat(str(raw_value))
        except ValueError:
            return None

    def _format_session_timestamp(self, raw_value: str) -> str:
        parsed = self._parse_session_datetime(raw_value)
        if parsed is None:
            return str(raw_value) if raw_value else "Unknown time"
        return parsed.strftime("%b %d, %Y %I:%M %p")

    def _session_preview(self, session: dict) -> str:
        messages = session.get("messages", [])
        first_user = ""
        for entry in messages:
            if entry.get("role") == "user":
                first_user = (entry.get("content") or "").strip()
                break
        if not first_user:
            return "No prompt preview"
        compact = " ".join(first_user.split())
        return f"{compact[:87]}..." if len(compact) > 90 else compact

    def show_history_mode(self, animated: bool = True) -> None:
        if self.drawer_stack.currentWidget() is self.history_widget:
            self.exit_history_mode(animated=animated)
            return
        if self._drawer_open and self.drawer_stack.currentWidget() is self.result_widget:
            self._history_return_target = "chat"
        else:
            self._history_return_target = "collapsed"
        self.drawer_stack.setCurrentWidget(self.history_widget)
        self.open_drawer(animated=animated)

    def show_chat_mode(self) -> None:
        self.drawer_stack.setCurrentWidget(self.result_widget)

    def exit_history_mode(self, animated: bool = True) -> None:
        self.show_chat_mode()
        if self._history_return_target == "collapsed":
            self.close_drawer(animated=animated)
        self._history_return_target = "chat"

    def _on_history_item_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if not session_id:
            return
        self._history_return_target = "chat"
        self.history_session_selected.emit(session_id)
        self.show_chat_mode()

    # ── Keyboard ─────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self.hide()
        event.ignore()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._drawer_open:
                if self.drawer_stack.currentWidget() is self.history_widget:
                    self.exit_history_mode(animated=True)
                    self.focus_input()
                    event.accept()
                    return
                self.close_drawer(animated=True)
                self.focus_input()
                event.accept()
                return
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)
