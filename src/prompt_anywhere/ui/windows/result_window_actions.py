"""Mixin-style helpers for ResultWindow actions.

Kept separate so ResultWindow.py doesn't become a god file.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QPushButton

from prompt_anywhere.ui.windows._code_block_utils import extract_fenced_code_blocks


def copy_to_clipboard(text: str) -> None:
    cb = QApplication.clipboard()
    cb.setText(text or "")


def rebuild_code_block_buttons(
    layout,
    code_blocks: list[str],
    on_copy,
):
    # clear
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()

    if not code_blocks:
        return

    for i, code in enumerate(code_blocks, start=1):
        btn = QPushButton(f"Copy code {i}")
        btn.setFixedHeight(22)
        btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(50, 50, 50, 120);
                color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                padding: 2px 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 8.5pt;
            }
            QPushButton:hover {
                background-color: rgba(70, 70, 70, 160);
            }
            """
        )
        btn.clicked.connect(lambda _=False, c=code: on_copy(c))
        layout.addWidget(btn)

    layout.addStretch(1)


def update_code_block_bar(bar_widget, bar_layout, assistant_text: str, on_copy):
    blocks = extract_fenced_code_blocks(assistant_text)
    rebuild_code_block_buttons(bar_layout, blocks, on_copy)
    bar_widget.setVisible(bool(blocks))
    return blocks
