"""Minimal drawer jitter probe (no layouts).

Purpose:
- Reproduce drawer open/close behavior with manual geometry only.
- Compare visual stability with/without window geometry animation.
- Keep bottom "prompt" section pinned while drawer opens between header and prompt.

Run:
    python tools/drawer_jitter_probe.py
"""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import QEasingCurve, Qt, QVariantAnimation
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QWidget


class DrawerJitterProbe(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setStyleSheet("background: rgba(20, 20, 20, 220); border: 1px solid rgba(255,255,255,0.2);")

        self.base_width = 700
        self.header_h = 36
        self.prompt_h = 80
        self.drawer_open_h = 260
        self.drawer_h = 0
        self.animate = False
        self.animate_window = False
        self.is_open = False
        self.anim: Optional[QVariantAnimation] = None

        self.title = QLabel("Drawer Jitter Probe", self)
        self.toggle_btn = QPushButton("Toggle Drawer", self)
        self.anim_btn = QPushButton("Animate: OFF", self)
        self.window_anim_btn = QPushButton("Window Anim: OFF", self)
        self.close_btn = QPushButton("X", self)
        self.close_shortcut = QShortcut(QKeySequence("Esc"), self)

        self.drawer = QWidget(self)
        self.drawer.setStyleSheet("background: rgba(255, 157, 92, 50); border: 1px solid rgba(255, 157, 92, 150);")
        self.drawer_label = QLabel("Drawer Area", self.drawer)

        self.prompt = QWidget(self)
        self.prompt.setStyleSheet("background: rgba(255,255,255,20); border: 1px solid rgba(255,255,255,80);")
        self.input = QLineEdit(self.prompt)
        self.input.setPlaceholderText("Prompt input (should stay visually stable)")
        self.send = QPushButton("Send", self.prompt)

        self.title.setStyleSheet("color: #FF9D5C; background: transparent;")
        self.drawer_label.setStyleSheet("color: white; background: transparent;")
        self.input.setStyleSheet("background: rgba(0,0,0,120); color: white; padding: 4px;")

        self.toggle_btn.clicked.connect(self.toggle_drawer)
        self.anim_btn.clicked.connect(self.toggle_animation)
        self.window_anim_btn.clicked.connect(self.toggle_window_animation)
        self.close_btn.clicked.connect(self.close)
        self.close_shortcut.activated.connect(self.close)

        self.resize(self.base_width, self.header_h + self.prompt_h + 12)
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            x = avail.x() + max(20, (avail.width() - self.width()) // 2)
            y = avail.y() + max(120, (avail.height() - self.height()) // 3)
            self.move(x, y)
        else:
            self.move(200, 260)
        self._apply_geometry()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_geometry()

    def toggle_animation(self) -> None:
        self.animate = not self.animate
        self.anim_btn.setText(f"Animate: {'ON' if self.animate else 'OFF'}")

    def toggle_window_animation(self) -> None:
        self.animate_window = not self.animate_window
        self.window_anim_btn.setText(f"Window Anim: {'ON' if self.animate_window else 'OFF'}")

    def toggle_drawer(self) -> None:
        target = self.drawer_open_h if not self.is_open else 0
        self.is_open = not self.is_open
        if not self.animate:
            self._set_drawer_height(target, apply_window_resize=True)
            return

        if self.anim is not None:
            self.anim.stop()
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(180)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(self.drawer_h)
        self.anim.setEndValue(target)
        self.anim.valueChanged.connect(
            lambda value: self._set_drawer_height(
                int(value),
                apply_window_resize=self.animate_window,
            )
        )
        self.anim.finished.connect(
            lambda: self._set_drawer_height(target, apply_window_resize=True)
        )
        self.anim.start()

    def _set_drawer_height(self, value: int, apply_window_resize: bool) -> None:
        bottom = self.y() + self.height()
        self.drawer_h = max(0, value)
        if apply_window_resize:
            new_h = self.header_h + self.prompt_h + self.drawer_h + 12
            self.setGeometry(self.x(), bottom - new_h, self.width(), new_h)
        self._apply_geometry()

    def _apply_geometry(self) -> None:
        w = self.width()

        self.title.setGeometry(10, 8, 180, 20)
        self.toggle_btn.setGeometry(200, 6, 120, 24)
        self.anim_btn.setGeometry(326, 6, 100, 24)
        self.window_anim_btn.setGeometry(432, 6, 120, 24)
        self.close_btn.setGeometry(w - 30, 6, 22, 24)

        drawer_top = self.header_h + 4
        self.drawer.setGeometry(8, drawer_top, w - 16, self.drawer_h)
        self.drawer_label.setGeometry(8, 8, 150, 20)
        self.drawer.setVisible(self.drawer_h > 0)

        prompt_top = drawer_top + self.drawer_h + 4
        self.prompt.setGeometry(8, prompt_top, w - 16, self.prompt_h)
        self.input.setGeometry(8, 10, self.prompt.width() - 90, 30)
        self.send.setGeometry(self.prompt.width() - 74, 10, 66, 30)


def main() -> int:
    app = QApplication(sys.argv)
    win = DrawerJitterProbe()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
