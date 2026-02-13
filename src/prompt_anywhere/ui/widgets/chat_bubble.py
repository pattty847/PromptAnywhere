"""Per-message chat bubble widget for the conversation drawer.

Each message gets its own QFrame with role header, auto-sizing text
content, and a hover-visible copy button for assistant messages.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
)

from prompt_anywhere.ui.common.assets import get_asset_path


class _BubbleTextDisplay(QTextBrowser):
    """Auto-sizing text area that grows with content (no internal scroll)."""

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().contentsChanged.connect(self._update_height)
        self.setStyleSheet(
            """
            QTextBrowser {
                background: transparent;
                color: #FFFFFF;
                border: none;
                padding: 0px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10pt;
                selection-background-color: rgba(255, 157, 92, 0.35);
            }
            """
        )
        self._update_height()

    def _update_height(self) -> None:
        doc_height = self.document().size().toSize().height()
        margins = self.contentsMargins()
        h = max(18, doc_height + margins.top() + margins.bottom())
        self.setFixedHeight(h)


class ChatBubble(QFrame):
    """Single message bubble (user or assistant)."""

    def __init__(self, role: str, content: str = "", parent=None) -> None:
        super().__init__(parent)
        self._role = role
        self._content = content
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("chatBubble")
        is_user = self._role == "user"

        bg = "rgba(45, 40, 55, 180)" if is_user else "rgba(28, 28, 32, 200)"
        border = "rgba(255, 157, 92, 0.2)" if is_user else "rgba(255, 255, 255, 0.08)"
        self.setStyleSheet(
            f"""
            QFrame#chatBubble {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(2)

        # Header row: role label + copy button
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)

        role_color = "#FF9D5C" if is_user else "rgba(255, 255, 255, 0.55)"
        role_text = "You" if is_user else "Assistant"
        role_label = QLabel(role_text)
        role_label.setStyleSheet(
            f"""
            QLabel {{
                color: {role_color};
                font-family: 'Segoe UI', sans-serif;
                font-size: 8pt;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 0px;
            }}
            """
        )
        header.addWidget(role_label)
        header.addStretch()

        if not is_user:
            self._copy_btn = QPushButton()
            self._copy_btn.setFixedSize(22, 22)
            self._copy_btn.setToolTip("Copy message")
            self._copy_btn.setVisible(False)
            self._copy_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.06);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 4px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.14);
                    border: 1px solid rgba(255, 157, 92, 0.4);
                }
                """
            )
            icon = QIcon(get_asset_path("copy.svg"))
            if not icon.isNull():
                self._copy_btn.setIcon(icon)
                self._copy_btn.setIconSize(QSize(14, 14))
            else:
                self._copy_btn.setText("C")
            self._copy_btn.clicked.connect(self._copy_content)
            header.addWidget(self._copy_btn)

        layout.addLayout(header)

        # Content
        self._text_widget = _BubbleTextDisplay()
        if self._content:
            self._text_widget.setPlainText(self._content)
        layout.addWidget(self._text_widget)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    # -- Public API -----------------------------------------------------------

    def append_content(self, text: str) -> None:
        """Append streaming text (cursor-based, efficient)."""
        self._content += text
        cursor = self._text_widget.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self._text_widget.setTextCursor(cursor)

    def get_content(self) -> str:
        """Return the full message content."""
        return self._content

    def set_content(self, text: str) -> None:
        """Replace the full message content."""
        self._content = text
        self._text_widget.setPlainText(text)

    # -- Hover copy -----------------------------------------------------------

    def enterEvent(self, event) -> None:
        if hasattr(self, "_copy_btn"):
            self._copy_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if hasattr(self, "_copy_btn"):
            self._copy_btn.setVisible(False)
        super().leaveEvent(event)

    def _copy_content(self) -> None:
        cb = QApplication.clipboard()
        cb.setText(self._content)
