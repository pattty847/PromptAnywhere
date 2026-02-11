"""Single-window shell with a chat drawer.

This keeps PromptAnywhere in one floating surface:
- bottom: prompt bar (MainPromptWindow in embedded mode)
- top: collapsible chat drawer (ResultWindow in embedded mode)

Scaffolding: minimal wiring so we can iterate on UX quickly.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from prompt_anywhere.ui.windows.main_prompt_window import MainPromptWindow
from prompt_anywhere.ui.windows.result_window import ResultWindow


class PromptShellWindow(QWidget):
    """Main always-on-top window containing prompt + drawer.

    Owns window dragging when embedded children are used.
    """

    prompt_submitted = Signal(str, object)  # prompt, image_bytes
    feature_triggered = Signal(str, str)  # feature_name, prompt
    follow_up_submitted = Signal(str, object)  # prompt, image_bytes
    session_closed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drawer_open = False
        self._drawer_anim: QPropertyAnimation | None = None

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Drawer container (animated)
        self.drawer_frame = QFrame()
        self.drawer_frame.setObjectName("chatDrawer")
        self.drawer_frame.setStyleSheet(
            """
            QFrame#chatDrawer {
                background: transparent;
            }
            """
        )
        self.drawer_layout = QVBoxLayout()
        self.drawer_layout.setContentsMargins(0, 0, 0, 0)
        self.drawer_layout.setSpacing(0)
        self.drawer_frame.setLayout(self.drawer_layout)

        self.result_widget = ResultWindow(embedded=True)
        self.drawer_layout.addWidget(self.result_widget)

        # Start collapsed
        self.drawer_frame.setMaximumHeight(0)
        self.drawer_frame.setVisible(False)

        # Prompt bar
        self.prompt_widget = MainPromptWindow(embedded=True)

        layout.addWidget(self.drawer_frame)
        layout.addWidget(self.prompt_widget)
        self.setLayout(layout)

        # Wire signals
        self.prompt_widget.prompt_submitted.connect(self._on_prompt_submitted)
        self.prompt_widget.feature_triggered.connect(self.feature_triggered)

        self.result_widget.follow_up_submitted.connect(self.follow_up_submitted)
        self.result_widget.session_closed.connect(self.session_closed)

        # Size: start as prompt height, drawer hidden
        self.adjustSize()

    def _on_prompt_submitted(self, prompt: str, image_bytes: object) -> None:
        # Open drawer immediately when a prompt is sent.
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
        self._drawer_open = True
        self.drawer_frame.setVisible(True)
        self._animate_drawer(target_height=520, animated=animated)

    def close_drawer(self, animated: bool = True) -> None:
        if not self._drawer_open:
            return
        self._drawer_open = False
        # animate to 0 then hide
        self._animate_drawer(target_height=0, animated=animated, hide_on_zero=True)

    def _animate_drawer(self, target_height: int, animated: bool, hide_on_zero: bool = False) -> None:
        if self._drawer_anim is not None:
            self._drawer_anim.stop()

        if not animated:
            self.drawer_frame.setMaximumHeight(target_height)
            if hide_on_zero and target_height == 0:
                self.drawer_frame.setVisible(False)
            self.adjustSize()
            return

        anim = QPropertyAnimation(self.drawer_frame, b"maximumHeight")
        anim.setDuration(160)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(self.drawer_frame.maximumHeight())
        anim.setEndValue(target_height)

        def on_finished() -> None:
            if hide_on_zero and target_height == 0:
                self.drawer_frame.setVisible(False)
            self.adjustSize()

        anim.finished.connect(on_finished)
        self._drawer_anim = anim
        anim.start()

    def focus_input(self) -> None:
        self.prompt_widget.input_field.setFocus()

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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._drawer_open:
                self.close_drawer(animated=True)
                self.focus_input()
                event.accept()
                return
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)
