"""History window for chat sessions."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal


class HistoryWindow(QWidget):
    """Simple history list window."""

    session_selected = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 520)
        self.sessions = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("History")
        title.setStyleSheet("""
            QLabel {
                color: #FF9D5C;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12pt;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: rgba(22, 22, 22, 230);
                color: #FFFFFF;
                border: 1px solid rgba(255, 157, 92, 0.3);
                border-radius: 6px;
                padding: 6px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 9pt;
            }
            QListWidget::item:selected {
                background-color: rgba(255, 157, 92, 0.2);
                border-radius: 4px;
            }
        """)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        self.setLayout(layout)

    def set_sessions(self, sessions):
        """Load sessions into the list."""
        self.sessions = sessions
        self.list_widget.clear()
        for session in sessions:
            created_at = session.get("created_at", "")
            msg_count = len(session.get("messages", []))
            label = f"{created_at} ({msg_count} messages)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, session.get("id"))
            self.list_widget.addItem(item)

    def on_item_clicked(self, item):
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id:
            self.session_selected.emit(session_id)
