"""Single-window shell with a chat drawer.

This keeps PromptAnywhere in one floating surface:
- top: shell header (title + close)
- middle: collapsible chat drawer (ResultWindow in embedded content mode)
- bottom: prompt panel (MainPromptWindow in embedded content mode)
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, Qt, Signal, QSize, QVariantAnimation
from PySide6.QtGui import QPixmap
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
        self._history_return_target = "collapsed"
        self._drawer_bottom_anchor: int | None = None
        self._saved_size_constraint: QLayout.SizeConstraint | None = None
        self._saved_min_height: int | None = None
        self._ui_debug_enabled = self._is_debug_enabled()
        self._last_anim_debug_ts = 0.0

        self.setup_ui()

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
        self._content_layout.setSpacing(4)

    def _build_header(self):
        """Build shell header row with title and close button."""
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
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
        self.drawer_frame = QFrame()
        self.drawer_frame.setObjectName("chatDrawer")
        self.drawer_frame.setStyleSheet("QFrame#chatDrawer { background: transparent; border: none; }")
        self.drawer_layout = QVBoxLayout()
        self.drawer_layout.setContentsMargins(0, 0, 0, 4)
        self.drawer_layout.setSpacing(0)
        self.drawer_frame.setLayout(self.drawer_layout)

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
        self.drawer_frame.setMaximumHeight(0)
        self.drawer_frame.setVisible(False)

        self.prompt_widget = MainPromptWindow(embedded=True, show_chrome=False)
        self.prompt_widget.setObjectName("promptPanel")
        self.result_widget.setObjectName("chatPanel")
        self.drawer_frame.setObjectName("drawerFrame")
        self.drawer_stack.setObjectName("drawerStack")

        self._content_layout.addWidget(self.drawer_frame)
        self._content_layout.addWidget(self.prompt_widget)

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
        self.setMinimumWidth(self.prompt_widget.window_width)
        self.resize(self.prompt_widget.window_width, self.prompt_widget.window_height + 24)
        self.adjustSize()
        self.update_window_mask()
        self.update_background_pixmap()
        self._setup_ui_debugging()
        self._debug_dump_layout("initialized")

    def _is_debug_enabled(self) -> bool:
        raw = os.environ.get("PROMPT_ANYWHERE_UI_DEBUG", "0").strip().lower()
        return raw in {"1", "true", "on", "yes"}

    def _setup_ui_debugging(self) -> None:
        """Install event filters for layout/geometry tracing in debug mode."""
        if not self._ui_debug_enabled:
            return
        watched = [
            self,
            self.drawer_frame,
            self.drawer_stack,
            self.result_widget,
            self.history_widget,
            self.prompt_widget,
            self.prompt_widget.input_field,
        ]
        for widget in watched:
            widget.installEventFilter(self)
        print("[UI_DEBUG] PromptShellWindow debug mode enabled.")

    def _debug(self, message: str) -> None:
        if self._ui_debug_enabled:
            print(f"[UI_DEBUG] {message}")

    def _widget_summary(self, widget: QWidget) -> str:
        geom = widget.geometry()
        size_hint = widget.sizeHint()
        return (
            f"{widget.objectName() or widget.__class__.__name__}: "
            f"xy=({geom.x()},{geom.y()}) size=({geom.width()}x{geom.height()}) "
            f"min=({widget.minimumWidth()}x{widget.minimumHeight()}) "
            f"max=({widget.maximumWidth()}x{widget.maximumHeight()}) "
            f"hint=({size_hint.width()}x{size_hint.height()})"
        )

    def _debug_dump_layout(self, tag: str) -> None:
        """Dump geometry/sizing of important widgets."""
        if not self._ui_debug_enabled:
            return
        self._debug(f"--- {tag} ---")
        widgets = [
            self,
            self.drawer_frame,
            self.drawer_stack,
            self.result_widget,
            self.history_widget,
            self.prompt_widget,
            self.prompt_widget.input_field,
        ]
        for widget in widgets:
            self._debug(self._widget_summary(widget))

    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:
        """Trace move/resize/layout events for key widgets."""
        if self._ui_debug_enabled:
            interesting = {
                QEvent.Type.Resize: "Resize",
                QEvent.Type.Move: "Move",
                QEvent.Type.Show: "Show",
                QEvent.Type.Hide: "Hide",
                QEvent.Type.LayoutRequest: "LayoutRequest",
            }
            label = interesting.get(event.type())
            if label:
                self._debug(
                    f"{label} -> {watched.objectName() or watched.__class__.__name__}: "
                    f"{self._widget_summary(watched)}"
                )
        return super().eventFilter(watched, event)

    def get_background_path(self) -> str:
        """Return the background image path."""
        return get_asset_path("background.png")

    def update_background_pixmap(self) -> None:
        """Scale and apply the background image to the shell container."""
        common_update_background_pixmap(
            self.background_label, self.background_pixmap, self.container.size()
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_window_mask()
        self.update_background_pixmap()

    def update_window_mask(self) -> None:
        """Clip shell to rounded corners so background image doesn't bleed at edges."""
        apply_rounded_mask(self, radius=16)

    def _on_prompt_submitted(self, prompt: str, image_bytes: object) -> None:
        self.open_drawer(animated=True)
        self.prompt_submitted.emit(prompt, image_bytes)

    def is_drawer_open(self) -> bool:
        return self._drawer_open

    def toggle_drawer(self, animated: bool = True) -> None:
        if self._drawer_open:
            self.close_drawer(animated=animated)
        else:
            self.open_drawer(animated=animated)

    def open_drawer(self, animated: bool = True) -> None:
        if self._drawer_open:
            return
        self._debug_dump_layout("open_drawer/before")
        self._drawer_open = True
        self._drawer_bottom_anchor = self.y() + self.height()
        self.drawer_frame.setVisible(True)
        self._resize_preserve_bottom(self._drawer_bottom_anchor)
        self._animate_drawer(target_height=self._drawer_open_height, animated=animated)

    def close_drawer(self, animated: bool = True) -> None:
        if not self._drawer_open:
            return
        self._debug_dump_layout("close_drawer/before")
        self._drawer_open = False
        self._drawer_bottom_anchor = self.y() + self.height()
        self._animate_drawer(target_height=0, animated=animated, hide_on_zero=True)

    def _animate_drawer(self, target_height: int, animated: bool, hide_on_zero: bool = False) -> None:
        if self._drawer_anim is not None:
            self._drawer_anim.stop()
            self._drawer_anim = None
            self._end_drawer_transition()
        if self._drawer_bottom_anchor is None:
            self._drawer_bottom_anchor = self.y() + self.height()
        self._begin_drawer_transition()
        self._debug(
            f"animate_drawer start: target_height={target_height} "
            f"animated={animated} anchor={self._drawer_bottom_anchor}"
        )

        if not animated:
            self._resize_preserve_bottom(self._drawer_bottom_anchor)
            self.drawer_frame.setMaximumHeight(target_height)
            if hide_on_zero and target_height == 0:
                self.drawer_frame.setVisible(False)
            self._resize_preserve_bottom(self._drawer_bottom_anchor)
            self._debug_dump_layout("animate_drawer/non_animated_done")
            self._end_drawer_transition()
            self._drawer_bottom_anchor = None
            return

        anim = QVariantAnimation()
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(self.drawer_frame.maximumHeight())
        anim.setEndValue(target_height)
        anim.valueChanged.connect(self._on_drawer_anim_value_changed)

        def on_finished() -> None:
            if hide_on_zero and target_height == 0:
                self.drawer_frame.setVisible(False)
            self._resize_preserve_bottom(self._drawer_bottom_anchor)
            self._debug_dump_layout("animate_drawer/finished")
            self._end_drawer_transition()
            self._drawer_bottom_anchor = None

        anim.finished.connect(on_finished)
        self._drawer_anim = anim
        anim.start()

    def _begin_drawer_transition(self) -> None:
        """Relax layout constraints so animation controls geometry cleanly."""
        layout = self.layout()
        if layout is not None and self._saved_size_constraint is None:
            self._saved_size_constraint = layout.sizeConstraint()
            layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        if self._saved_min_height is None:
            self._saved_min_height = self.minimumHeight()
        self.setMinimumHeight(0)

    def _end_drawer_transition(self) -> None:
        """Restore constraints after animation completes."""
        layout = self.layout()
        if layout is not None and self._saved_size_constraint is not None:
            layout.setSizeConstraint(self._saved_size_constraint)
        self._saved_size_constraint = None
        if self._saved_min_height is not None:
            self.setMinimumHeight(self._saved_min_height)
        self._saved_min_height = None

    def _on_drawer_anim_value_changed(self, value) -> None:
        """Keep bottom fixed during animation and optionally trace frame states."""
        self.setUpdatesEnabled(False)
        self.drawer_frame.setMaximumHeight(int(value))
        self._resize_preserve_bottom(self._drawer_bottom_anchor)
        self.setUpdatesEnabled(True)
        if not self._ui_debug_enabled:
            return
        now = time.perf_counter()
        if now - self._last_anim_debug_ts < 0.06:
            return
        self._last_anim_debug_ts = now
        self._debug(
            f"anim tick: drawer_max_h={int(value)} "
            f"shell_pos=({self.x()},{self.y()}) shell_size=({self.width()}x{self.height()}) "
            f"anchor={self._drawer_bottom_anchor}"
        )

    def _resize_preserve_bottom(self, bottom_anchor: int | None = None) -> None:
        """Resize to layout while keeping the window bottom edge fixed on screen."""
        if bottom_anchor is None:
            bottom_anchor = self.y() + self.height()
        layout = self.layout()
        if layout is not None:
            layout.activate()
        new_height = max(self.minimumHeight(), self.sizeHint().height())
        self.setGeometry(self.x(), bottom_anchor - new_height, self.width(), new_height)

    def focus_input(self) -> None:
        self.prompt_widget.input_field.setFocus()

    def set_available_agents(self, agent_names: list[str]) -> None:
        """Update compact model dropdown options in embedded prompt panel."""
        self.prompt_widget.set_available_agents(agent_names)

    def set_selected_agent(self, agent_name: str) -> None:
        """Set active model selection in embedded prompt panel."""
        self.prompt_widget.set_selected_agent(agent_name)

    def set_streaming_state(self, active: bool) -> None:
        """Toggle prompt send button between Send and Stop modes."""
        self.prompt_widget.set_streaming_state(active)

    def _build_history_widget(self) -> QWidget:
        """Create in-drawer history panel."""
        panel = QWidget()
        layout = QVBoxLayout()
        # Keep some breathing room around the history list container.
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
        """Populate the in-drawer history list."""
        self.history_list.clear()
        sorted_sessions = sorted(
            sessions,
            key=lambda session: self._session_sort_key(session),
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
        """Sort sessions by latest activity timestamp."""
        ts_raw = session.get("updated_at") or session.get("created_at") or ""
        parsed = self._parse_session_datetime(ts_raw)
        if parsed is not None:
            return parsed
        return datetime.min

    def _parse_session_datetime(self, raw_value: str) -> datetime | None:
        """Parse ISO-like timestamps used by saved sessions."""
        if not raw_value:
            return None
        try:
            return datetime.fromisoformat(str(raw_value))
        except ValueError:
            return None

    def _format_session_timestamp(self, raw_value: str) -> str:
        """Format session timestamp for history list display."""
        parsed = self._parse_session_datetime(raw_value)
        if parsed is None:
            return str(raw_value) if raw_value else "Unknown time"
        return parsed.strftime("%b %d, %Y %I:%M %p")

    def _session_preview(self, session: dict) -> str:
        """Return a concise preview line for a session."""
        messages = session.get("messages", [])
        first_user = ""
        for entry in messages:
            if entry.get("role") == "user":
                first_user = (entry.get("content") or "").strip()
                break
        if not first_user:
            return "No prompt preview"
        compact = " ".join(first_user.split())
        if len(compact) > 90:
            return f"{compact[:87]}..."
        return compact

    def show_history_mode(self, animated: bool = True) -> None:
        """Switch drawer content to history list."""
        if self.drawer_stack.currentWidget() is self.history_widget:
            self.exit_history_mode(animated=animated)
            return
        self._debug_dump_layout("show_history_mode/before")
        if self._drawer_open and self.drawer_stack.currentWidget() is self.result_widget:
            self._history_return_target = "chat"
        else:
            self._history_return_target = "collapsed"
        self.drawer_stack.setCurrentWidget(self.history_widget)
        self.open_drawer(animated=animated)
        self._debug_dump_layout("show_history_mode/after")

    def show_chat_mode(self) -> None:
        """Switch drawer content back to chat transcript."""
        self.drawer_stack.setCurrentWidget(self.result_widget)
        self._debug_dump_layout("show_chat_mode")

    def exit_history_mode(self, animated: bool = True) -> None:
        """Exit history view using the appropriate return target."""
        self._debug(f"exit_history_mode return_target={self._history_return_target}")
        self.show_chat_mode()
        if self._history_return_target == "collapsed":
            self.close_drawer(animated=animated)
        self._history_return_target = "chat"

    def _on_history_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle selecting a session in history mode."""
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if not session_id:
            return
        self._history_return_target = "chat"
        self.history_session_selected.emit(session_id)
        self.show_chat_mode()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and getattr(self, "_drag_pos", None) is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def closeEvent(self, event):
        """Hide instead of closing so the hotkey can re-open instantly."""
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
