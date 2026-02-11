"""Screenshot selection overlay window"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QColor, QPen
from PIL import ImageGrab
from io import BytesIO


class ScreenshotOverlay(QWidget):
    """Fullscreen transparent overlay for region selection"""
    screenshot_taken = Signal(bytes)
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.showFullScreen()
        
        self.start_pos = None
        self.current_pos = None
    
    def paintEvent(self, event):
        """Draw selection rectangle"""
        painter = QPainter(self)
        
        # Dim background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if self.start_pos and self.current_pos:
            # Clear selected area
            rect = QRect(self.start_pos, self.current_pos).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            
            # Draw border
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(0, 120, 215), 3))
            painter.drawRect(rect)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()
    
    def mouseMoveEvent(self, event):
        if self.start_pos:
            self.current_pos = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.start_pos and self.current_pos:
            rect = QRect(self.start_pos, self.current_pos).normalized()
            
            # Capture screenshot of selected region
            screenshot = ImageGrab.grab(bbox=(
                rect.x(),
                rect.y(),
                rect.x() + rect.width(),
                rect.y() + rect.height()
            ))
            
            # Convert to bytes
            buf = BytesIO()
            screenshot.save(buf, format='PNG')
            self.screenshot_taken.emit(buf.getvalue())
            self.close()
    
    def keyPressEvent(self, event):
        """ESC to cancel"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
