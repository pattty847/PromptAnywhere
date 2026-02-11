"""Prompt input window"""
import sys
from PySide6.QtWidgets import QWidget, QTextEdit, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QCursor
from prompt_anywhere.ui.windows.screenshot_overlay import ScreenshotOverlay
from prompt_anywhere.core.utils.platform_utils import apply_blur_effect


class PromptInputWindow(QWidget):
    """Input window for entering prompts and attaching screenshots"""
    prompt_submitted = Signal(str, object)  # prompt, image_bytes
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(600, 150)
        
        # Position at cursor
        cursor_pos = QCursor.pos()
        self.move(cursor_pos.x() - 300, cursor_pos.y() - 75)
        
        self.screenshot_bytes = None
        self.screenshot_overlay = None
        self.drag_position = None
        
        self.setup_ui()
        self.apply_blur_effect()
    
    def setup_ui(self):
        """Create UI elements"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Container
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 15, 15, 120);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(15, 15, 15, 15)
        container_layout.setSpacing(10)
        
        # Title
        title = QLabel("Ask Gemini")
        title.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12pt;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        container_layout.addWidget(title)
        
        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your question...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: rgba(50, 50, 50, 200);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11pt;
                selection-background-color: rgba(0, 120, 215, 128);
            }
            QLineEdit:focus {
                border: 1px solid rgba(0, 120, 215, 255);
            }
        """)
        self.input_field.returnPressed.connect(self.submit_prompt)
        container_layout.addWidget(self.input_field)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Screenshot status label
        self.screenshot_label = QLabel("")
        self.screenshot_label.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-family: 'Segoe UI', sans-serif;
                font-size: 9pt;
                background: transparent;
                border: none;
            }
        """)
        button_layout.addWidget(self.screenshot_label)
        
        button_layout.addStretch()
        
        # Screenshot button
        self.screenshot_btn = QPushButton("📷 Screenshot")
        self.screenshot_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(70, 70, 70, 200);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 8px 16px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: rgba(90, 90, 90, 220);
            }
            QPushButton:pressed {
                background-color: rgba(50, 50, 50, 200);
            }
        """)
        self.screenshot_btn.clicked.connect(self.capture_screenshot)
        button_layout.addWidget(self.screenshot_btn)
        
        # Send button
        self.send_btn = QPushButton("Send")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 120, 215, 200);
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0, 140, 235, 220);
            }
            QPushButton:pressed {
                background-color: rgba(0, 100, 195, 200);
            }
        """)
        self.send_btn.clicked.connect(self.submit_prompt)
        button_layout.addWidget(self.send_btn)
        
        container_layout.addLayout(button_layout)
        
        self.container.setLayout(container_layout)
        layout.addWidget(self.container)
        self.setLayout(layout)
        
        # Focus input field
        self.input_field.setFocus()
    
    def apply_blur_effect(self):
        """Apply Windows blur effect (acrylic/mica style)"""
        if sys.platform == 'win32':
            hwnd = int(self.winId())
            apply_blur_effect(hwnd)
    
    def capture_screenshot(self):
        """Open screenshot overlay"""
        self.hide()
        self.screenshot_overlay = ScreenshotOverlay()
        self.screenshot_overlay.screenshot_taken.connect(self.on_screenshot_captured)
        self.screenshot_overlay.show()
    
    @Slot(bytes)
    def on_screenshot_captured(self, image_bytes):
        """Handle captured screenshot"""
        self.screenshot_bytes = image_bytes
        self.screenshot_label.setText("✓ Screenshot attached")
        self.screenshot_overlay = None
        self.show()
        self.input_field.setFocus()
    
    def submit_prompt(self):
        """Submit prompt with optional screenshot"""
        prompt = self.input_field.text().strip()
        if not prompt:
            return
        
        self.prompt_submitted.emit(prompt, self.screenshot_bytes)
        self.close()
    
    def mousePressEvent(self, event):
        """Enable window dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        """Handle window dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
    
    def keyPressEvent(self, event):
        """ESC to close"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
