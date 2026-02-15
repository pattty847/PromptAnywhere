"""Single-window shell: header + collapsible drawer + prompt.

Animation approach (matches tools/drawer_jitter_probe.py):
- NO QVBoxLayout on the content area — children are positioned with
  setGeometry() in _apply_geometry(), exactly like the probe.
- _drawer_h tracks current drawer height in pixels (0 when closed).
- QVariantAnimation ticks call _set_drawer_height() which updates
  _drawer_h, resizes the window (bottom edge anchored), and calls
  _apply_geometry() to reposition children.
- setMask() and background rescale are SKIPPED during animation and
  applied once on finish.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QEasingCurve, QRect, Qt, Signal, QVariantAnimation
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
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
#  Geometry constants (match probe style)
# ---------------------------------------------------------------------------
_MARGIN = 5
_HEADER_H = 24
_GAP = 4
_RESIZE_GRIP = 8
_MIN_WIDTH = 420
_MIN_HEIGHT = 180
_ANIM_DURATION_MS = 180

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
    """Main always-on-top window: header + drawer + prompt."""

    prompt_submitted = Signal(str, object)
    feature_triggered = Signal(str, str)
    follow_up_submitted = Signal(str, object)
    session_closed = Signal()
    history_session_selected = Signal(str)
    agent_selected = Signal(str)
    stop_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Drawer state
        self._drawer_h: int = 0               # current drawer pixel height
        self._drawer_open: bool = False
        self._drawer_open_height: int = 380    # target height when open
        self._drawer_anim: Optional[QVariantAnimation] = None
        self._animating: bool = False
        self._history_return_target = "collapsed"

        # Resize state
        self._resize_edge: Optional[str] = None
        self._resize_start_global = None
        self._resize_start_geo: Optional[QRect] = None
        self._drag_pos = None

        # Debug
        self._ui_debug = os.environ.get(
            "PROMPT_ANYWHERE_UI_DEBUG", "0"
        ).strip().lower() in {"1", "true", "on", "yes"}

        self._build_ui()

    # ── Build ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # -- Background layering (only layout in the whole window) ----------
        self.container = QWidget(self)
        self.container.setStyleSheet(
            "QWidget { background: transparent; border-radius: 16px;"
            " border: 1px solid rgba(255,255,255,0.1); }"
        )
        self.background_label = FixedBackgroundLabel(self.container)
        self.background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.background_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self.background_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self.background_pixmap = QPixmap(get_asset_path("background.png"))

        self.content_widget = QWidget(self.container)
        self.content_widget.setStyleSheet(
            "QWidget { background-color: rgba(15,15,15,140);"
            " border-radius: 16px; }"
        )

        stack = QStackedLayout(self.container)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        stack.addWidget(self.background_label)
        stack.addWidget(self.content_widget)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.container)

        # -- Header (children of content_widget, NO layout) -----------------
        self.title_label = QLabel("Prompt Anywhere", self.content_widget)
        self.title_label.setStyleSheet(
            "QLabel { color: #FF9D5C; font-family: 'Segoe UI', sans-serif;"
            " font-size: 12pt; font-weight: bold; background: transparent;"
            " border: none; }"
        )

        self.close_btn = QPushButton("", self.content_widget)
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setStyleSheet(
            "QPushButton { background: transparent;"
            " color: rgba(255,255,255,0.6); border: none; }"
            " QPushButton:hover { color: rgba(255,255,255,1.0); }"
        )
        set_button_icon(
            self.close_btn,
            "close_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
            12,
        )
        self.close_btn.clicked.connect(self.hide)

        # -- Drawer (child of content_widget, internal layout is fine) ------
        self.drawer_frame = QFrame(self.content_widget)
        self.drawer_frame.setStyleSheet(
            "QFrame { background: transparent; border: none; }"
        )
        drawer_inner = QVBoxLayout(self.drawer_frame)
        drawer_inner.setContentsMargins(0, 0, 0, 0)
        drawer_inner.setSpacing(0)

        self.drawer_stack = QStackedWidget()
        self.drawer_stack.setStyleSheet(
            "QStackedWidget { background: transparent; border: none; }"
        )
        self.result_widget = ResultWindow(
            embedded=True, show_chrome=False, show_followup_input=False,
        )
        self.drawer_stack.addWidget(self.result_widget)
        self.history_widget = self._build_history_widget()
        self.drawer_stack.addWidget(self.history_widget)
        drawer_inner.addWidget(self.drawer_stack)

        self.drawer_frame.setVisible(False)

        # -- Prompt (child of content_widget) -------------------------------
        self.prompt_widget = MainPromptWindow(embedded=True, show_chrome=False)
        self.prompt_widget.setParent(self.content_widget)

        # -- Signals --------------------------------------------------------
        self.prompt_widget.prompt_submitted.connect(self._on_prompt_submitted)
        self.prompt_widget.feature_triggered.connect(self.feature_triggered)
        self.prompt_widget.agent_selected.connect(self.agent_selected)
        self.prompt_widget.stop_requested.connect(self.stop_requested)
        self.result_widget.follow_up_submitted.connect(self.follow_up_submitted)
        self.result_widget.session_closed.connect(self.session_closed)

        # -- Initial size ---------------------------------------------------
        self._prompt_h = self.prompt_widget.window_height  # 200
        self._collapsed_h = (
            _MARGIN + _HEADER_H + _GAP + self._prompt_h + _MARGIN
        )
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)
        self.resize(self.prompt_widget.window_width, self._collapsed_h)
        self._apply_geometry()
        self.update_window_mask()
        self.update_background_pixmap()

    # ── Manual geometry (the cure for jitter) ─────────────────────────────

    def _apply_geometry(self) -> None:
        """Position header / drawer / prompt by pixel math — no layout."""
        w = self.content_widget.width()

        # Header
        self.title_label.setGeometry(_MARGIN + 2, _MARGIN, 200, _HEADER_H)
        self.close_btn.setGeometry(w - _MARGIN - 22, _MARGIN, 20, 20)

        # Drawer
        drawer_top = _MARGIN + _HEADER_H + _GAP
        self.drawer_frame.setGeometry(
            _MARGIN, drawer_top, w - 2 * _MARGIN, self._drawer_h
        )
        self.drawer_frame.setVisible(self._drawer_h > 0)

        # Prompt (fills remaining space below drawer)
        gap_after = _GAP if self._drawer_h > 0 else 0
        prompt_top = drawer_top + self._drawer_h + gap_after
        prompt_h = self.content_widget.height() - prompt_top - _MARGIN
        self.prompt_widget.setGeometry(
            _MARGIN, prompt_top, w - 2 * _MARGIN, max(prompt_h, 100)
        )

    # ── Background / mask (expensive — skip during animation) ─────────────

    def update_background_pixmap(self) -> None:
        common_update_background_pixmap(
            self.background_label, self.background_pixmap, self.container.size()
        )

    def update_window_mask(self) -> None:
        apply_rounded_mask(self, radius=16)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_geometry()
        if not self._animating:
            self.update_window_mask()
            self.update_background_pixmap()

    # ── Drawer open / close ───────────────────────────────────────────────

    def is_drawer_open(self) -> bool:
        return self._drawer_open

    def toggle_drawer(self, animated: bool = True) -> None:
        if self._drawer_open:
            self.close_drawer(animated)
        else:
            self.open_drawer(animated)

    def open_drawer(self, animated: bool = True) -> None:
        if self._drawer_open:
            return
        self._drawer_open = True
        target = self._drawer_open_height

        if not animated:
            self._set_drawer_height(target, resize_window=True)
            self.update_window_mask()
            self.update_background_pixmap()
            return

        self._animating = True
        self._run_drawer_anim(self._drawer_h, target)

    def close_drawer(self, animated: bool = True) -> None:
        if not self._drawer_open:
            return
        self._drawer_open = False

        if not animated:
            self._set_drawer_height(0, resize_window=True)
            self.drawer_frame.setVisible(False)
            self.update_window_mask()
            self.update_background_pixmap()
            return

        self._animating = True
        self._run_drawer_anim(self._drawer_h, 0, hide_on_done=True)

    def _run_drawer_anim(
        self, start: int, end: int, hide_on_done: bool = False
    ) -> None:
        if self._drawer_anim is not None:
            self._drawer_anim.stop()

        anim = QVariantAnimation(self)
        anim.setDuration(_ANIM_DURATION_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.valueChanged.connect(
            lambda v: self._set_drawer_height(int(v), resize_window=True)
        )

        def on_finished() -> None:
            self._set_drawer_height(end, resize_window=True)
            if hide_on_done:
                self.drawer_frame.setVisible(False)
            self._animating = False
            self._drawer_anim = None
            self.update_window_mask()
            self.update_background_pixmap()

        anim.finished.connect(on_finished)
        self._drawer_anim = anim
        anim.start()

    def _set_drawer_height(self, value: int, resize_window: bool) -> None:
        """Core of the animation — mirrors the probe exactly."""
        bottom = self.y() + self.height()
        self._drawer_h = max(0, value)
        if resize_window:
            extra = self._drawer_h + (_GAP if self._drawer_h > 0 else 0)
            new_h = self._collapsed_h + extra
            self.setGeometry(self.x(), bottom - new_h, self.width(), new_h)
        self._apply_geometry()

    # ── Prompt submission ─────────────────────────────────────────────────

    def _on_prompt_submitted(self, prompt: str, image_bytes: object) -> None:
        self.open_drawer(animated=True)
        self.prompt_submitted.emit(prompt, image_bytes)

    # ── Resize handles ────────────────────────────────────────────────────

    @staticmethod
    def _get_resize_edge(pos, size) -> Optional[str]:
        g = _RESIZE_GRIP
        x, y, w, h = pos.x(), pos.y(), size.width(), size.height()
        top = y <= g
        bot = y >= h - g
        lft = x <= g
        rgt = x >= w - g
        if top and lft: return "top-left"
        if top and rgt: return "top-right"
        if bot and lft: return "bottom-left"
        if bot and rgt: return "bottom-right"
        if top: return "top"
        if bot: return "bottom"
        if lft: return "left"
        if rgt: return "right"
        return None

    def _apply_resize(self, gpos) -> None:
        if self._resize_edge is None or self._resize_start_geo is None:
            return
        dx = gpos.x() - self._resize_start_global.x()
        dy = gpos.y() - self._resize_start_global.y()
        geo = QRect(self._resize_start_geo)
        e = self._resize_edge
        if "right" in e:  geo.setRight(self._resize_start_geo.right() + dx)
        if "left" in e:   geo.setLeft(self._resize_start_geo.left() + dx)
        if "bottom" in e: geo.setBottom(self._resize_start_geo.bottom() + dy)
        if "top" in e:    geo.setTop(self._resize_start_geo.top() + dy)
        if geo.width() < _MIN_WIDTH:
            if "left" in e: geo.setLeft(geo.right() - _MIN_WIDTH)
            else:           geo.setRight(geo.left() + _MIN_WIDTH)
        if geo.height() < _MIN_HEIGHT:
            if "top" in e: geo.setTop(geo.bottom() - _MIN_HEIGHT)
            else:          geo.setBottom(geo.top() + _MIN_HEIGHT)
        self.setGeometry(geo)

        # Auto-open drawer if user drags tall enough
        avail = geo.height() - self._collapsed_h
        if not self._drawer_open and avail > 40:
            self._drawer_open = True
            self._drawer_h = avail
            self._apply_geometry()

    # ── Mouse events ──────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        edge = self._get_resize_edge(event.position().toPoint(), self.size())
        if edge:
            self._resize_edge = edge
            self._resize_start_global = event.globalPosition().toPoint()
            self._resize_start_geo = QRect(self.geometry())
            event.accept()
            return
        self._drag_pos = (
            event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        )
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if (
            self._resize_edge is not None
            and event.buttons() == Qt.MouseButton.LeftButton
        ):
            self._apply_resize(event.globalPosition().toPoint())
            event.accept()
            return
        if (
            event.buttons() == Qt.MouseButton.LeftButton
            and self._drag_pos is not None
        ):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        if event.buttons() == Qt.MouseButton.NoButton:
            edge = self._get_resize_edge(
                event.position().toPoint(), self.size()
            )
            self.setCursor(_EDGE_CURSORS[edge]) if edge else self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._resize_edge is not None:
            self._resize_edge = None
            self._resize_start_global = None
            self._resize_start_geo = None
            event.accept()
            return
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ── Forwarded widget API ──────────────────────────────────────────────

    def focus_input(self) -> None:
        self.prompt_widget.input_field.setFocus()

    def set_available_agents(self, agents: list[str]) -> None:
        self.prompt_widget.set_available_agents(agents)

    def set_selected_agent(self, name: str) -> None:
        self.prompt_widget.set_selected_agent(name)

    def set_streaming_state(self, active: bool) -> None:
        self.prompt_widget.set_streaming_state(active)

    # ── History panel ─────────────────────────────────────────────────────

    def _build_history_widget(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(6, 4, 6, 6)
        lay.setSpacing(6)

        hdr = QVBoxLayout()
        hdr.setContentsMargins(7, 5, 0, 0)

        back_btn = QPushButton("Back")
        back_btn.setFixedHeight(24)
        back_btn.setStyleSheet(
            "QPushButton { background: rgba(50,50,50,150);"
            " color: rgba(255,255,255,0.9);"
            " border: 1px solid rgba(255,255,255,0.15);"
            " border-radius: 6px; font-size: 8pt; padding: 2px 10px; }"
            " QPushButton:hover { background: rgba(70,70,70,180); }"
        )
        back_btn.clicked.connect(
            lambda _=False: self.exit_history_mode(animated=True)
        )
        hdr.addWidget(back_btn)

        title = QLabel("History")
        title.setStyleSheet(
            "QLabel { color: #FF9D5C; font-family: 'Segoe UI', sans-serif;"
            " font-size: 11pt; font-weight: bold; background: transparent;"
            " border: none; }"
        )
        hdr.addWidget(title)
        lay.addLayout(hdr)

        self.history_list = QListWidget()
        self.history_list.setWordWrap(True)
        self.history_list.setUniformItemSizes(False)
        self.history_list.setStyleSheet(
            "QListWidget { background: rgba(22,22,22,230); color: #FFF;"
            " border: 1px solid rgba(255,157,92,0.3); border-radius: 6px;"
            " padding: 6px; font-size: 9pt; }"
            " QListWidget::item { padding: 6px 4px; }"
            " QListWidget::item:selected {"
            " background: rgba(255,157,92,0.2); border-radius: 4px; }"
        )
        self.history_list.itemClicked.connect(self._on_history_item_clicked)
        lay.addWidget(self.history_list, stretch=1)
        return panel

    def set_history_sessions(self, sessions: list[dict]) -> None:
        self.history_list.clear()
        for s in sorted(
            sessions,
            key=lambda s: self._parse_ts(
                s.get("updated_at") or s.get("created_at") or ""
            ) or datetime.min,
            reverse=True,
        ):
            n = len(s.get("messages", []))
            ts = self._fmt_ts(s.get("updated_at") or s.get("created_at") or "")
            preview = self._preview(s)
            item = QListWidgetItem(f"{ts}  ({n} messages)\n{preview}")
            item.setData(Qt.ItemDataRole.UserRole, s.get("id"))
            self.history_list.addItem(item)

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
        sid = item.data(Qt.ItemDataRole.UserRole)
        if not sid:
            return
        self._history_return_target = "chat"
        self.history_session_selected.emit(sid)
        self.show_chat_mode()

    # ── Timestamp helpers ─────────────────────────────────────────────────

    @staticmethod
    def _parse_ts(raw: str) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return None

    @classmethod
    def _fmt_ts(cls, raw: str) -> str:
        dt = cls._parse_ts(raw)
        return dt.strftime("%b %d, %Y %I:%M %p") if dt else (raw or "Unknown")

    @staticmethod
    def _preview(session: dict) -> str:
        for e in session.get("messages", []):
            if e.get("role") == "user":
                t = " ".join((e.get("content") or "").split())
                return (t[:87] + "...") if len(t) > 90 else t
        return "No prompt preview"

    # ── Keyboard ──────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self.hide()
        event.ignore()

    def keyPressEvent(self, event) -> None:
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
