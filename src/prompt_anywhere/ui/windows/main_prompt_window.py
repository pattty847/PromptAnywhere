"""Main prompt window matching UI prototype"""
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QGridLayout, QSizePolicy, QFrame, QLayout, QStackedLayout
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QCursor, QPixmap, QIcon
from prompt_anywhere.ui.windows.screenshot_overlay import ScreenshotOverlay
from prompt_anywhere.core.utils.platform_utils import apply_blur_effect


class FixedBackgroundLabel(QLabel):
    """Background label that does not affect layout sizing."""

    def sizeHint(self):
        return QSize(0, 0)


class MainPromptWindow(QWidget):
    """Main prompt UI.

    When `embedded=True`, the widget is meant to be hosted inside another window
    (e.g., PromptShellWindow) and should not set top-level window flags or
    reposition itself.
    """

    prompt_submitted = Signal(str, object)  # prompt, image_bytes
    feature_triggered = Signal(str, str)  # feature_name, prompt

    def __init__(self, embedded: bool = False, show_chrome: bool = True):
        super().__init__()
        self._embedded = embedded
        self._show_chrome = show_chrome
        if not embedded:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.window_width = 600
        self.window_height = 200
        self.min_window_size = QSize(self.window_width, self.window_height)
        self.setMinimumSize(self.min_window_size)
        self.font_scale = 2
        self.min_font_scale = -1
        self.max_font_scale = 3
        self.utility_buttons = []
        self.utility_button_icons = []
        self.feature_buttons = []
        self.feature_name_labels = []
        self.feature_hotkey_labels = []
        self.feature_icon_labels = []

        # Position at center of screen (top-level mode only)
        if not self._embedded:
            self.center_on_screen()

        self.screenshot_bytes = None
        self.screenshot_overlay = None
        self.drag_position = None

        self.setup_ui()
        if not self._embedded:
            self.apply_blur_effect()
            if self._show_chrome:
                self.update_window_mask()

    def center_on_screen(self):
        """Center window on screen"""
        from PySide6.QtGui import QScreen
        screen = QScreen.availableGeometry(self.screen())
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def setup_ui(self):
        """Create UI elements matching prototype"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        if self._show_chrome:
            # Main container
            self.container = QWidget()
            self.container.setStyleSheet("""
                QWidget {
                    background-color: transparent;
                    border-radius: 16px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }
            """)

            self.background_label = FixedBackgroundLabel()
            self.background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.background_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            self.background_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.background_pixmap = QPixmap(self.get_background_path())

            self.content_widget = QWidget()
            self.content_widget.setStyleSheet("""
                QWidget {
                    background-color: rgba(15, 15, 15, 140);
                    border-radius: 16px;
                }
            """)
        else:
            self.container = self
            self.background_pixmap = QPixmap()
            self.content_widget = QWidget()
            self.content_widget.setStyleSheet("QWidget { background: transparent; border: none; }")

        container_layout = QVBoxLayout()
        if self._show_chrome:
            container_layout.setContentsMargins(4, 4, 4, 4)
        else:
            # Embedded in shell: keep content close to shell edges.
            container_layout.setContentsMargins(4, 4, 4, 4)
        container_layout.setSpacing(4)

        # Header row with title and close button (top-level chrome mode).
        if self._show_chrome:
            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(0)

            self.title_label = QLabel("Prompt Anywhere")
            self.title_label.setStyleSheet(self.title_label_stylesheet())
            header_layout.addWidget(self.title_label)
            header_layout.addStretch()

            # Close button
            self.close_btn = QPushButton("X")
            self.close_btn.setFixedSize(20, 20)
            self.close_btn.setStyleSheet(self.close_button_stylesheet())
            self.close_btn.clicked.connect(self.close)
            header_layout.addWidget(self.close_btn)

            container_layout.addLayout(header_layout)

        # Input row with utility buttons
        input_row_layout = QHBoxLayout()
        input_row_layout.setContentsMargins(0, 0, 0, 0)
        input_row_layout.setSpacing(6)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask your CLI agents anything...")
        self.input_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.input_field.setFixedHeight(32)
        self.input_field.setStyleSheet(self.input_stylesheet())
        self.input_field.returnPressed.connect(self.submit_prompt)
        input_row_layout.addWidget(self.input_field)

        # Send button inline with input
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedSize(68, 32)
        self.send_btn.setStyleSheet(self.send_button_stylesheet())
        self.send_btn.clicked.connect(self.submit_prompt)
        input_row_layout.addWidget(self.send_btn)

        container_layout.addLayout(input_row_layout)

        # Utility buttons row (compact, below input)
        utility_buttons_layout = QHBoxLayout()
        utility_buttons_layout.setContentsMargins(0, 0, 0, 0)
        utility_buttons_layout.setSpacing(4)
        utility_buttons_layout.addStretch()

        self.screenshot_btn = self.create_utility_button("Screenshot", "screenshot")
        self.screenshot_btn.clicked.connect(self.capture_screenshot)
        utility_buttons_layout.addWidget(self.screenshot_btn)

        history_btn = self.create_utility_button("History", "history")
        history_btn.clicked.connect(lambda: self.trigger_feature("history"))
        utility_buttons_layout.addWidget(history_btn)

        grid_btn = self.create_utility_button("Grid", "grid")
        utility_buttons_layout.addWidget(grid_btn)

        settings_btn = self.create_utility_button("Settings", "settings")
        settings_btn.clicked.connect(lambda: self.trigger_feature("customize"))
        utility_buttons_layout.addWidget(settings_btn)

        container_layout.addLayout(utility_buttons_layout)

        # Feature buttons grid
        features_grid = QGridLayout()
        features_grid.setContentsMargins(0, 0, 0, 0)
        features_grid.setHorizontalSpacing(4)
        features_grid.setVerticalSpacing(4)

        # Row 1
        google_btn = self.create_feature_button("Google Search", "Ctrl + G", "google")
        google_btn.clicked.connect(lambda: self.trigger_feature("google_search"))
        features_grid.addWidget(google_btn, 0, 0)

        files_btn = self.create_feature_button("Search Files", "Ctrl + E", "files")
        files_btn.clicked.connect(lambda: self.trigger_feature("file_search"))
        features_grid.addWidget(files_btn, 0, 1)

        browser_btn = self.create_feature_button("Open Browser", "Ctrl + Shift + B", "browser")
        browser_btn.clicked.connect(lambda: self.trigger_feature("browser"))
        features_grid.addWidget(browser_btn, 0, 2)

        terminal_btn = self.create_feature_button("New Terminal", "Ctrl + J", "terminal")
        terminal_btn.clicked.connect(lambda: self.trigger_feature("terminal"))
        features_grid.addWidget(terminal_btn, 0, 3)

        maximize_btn = self.create_feature_button("Maximize Chat", "Ctrl + Alt + E", "maximize")
        maximize_btn.clicked.connect(lambda: self.trigger_feature("maximize_chat"))
        features_grid.addWidget(maximize_btn, 0, 4)

        feature_container = QWidget()
        feature_container.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 20, 60);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        feature_container_layout = QVBoxLayout()
        feature_container_layout.setContentsMargins(5, 5, 5, 5)
        feature_container_layout.setSpacing(0)
        feature_container_layout.addLayout(features_grid)
        feature_container.setLayout(feature_container_layout)
        container_layout.addWidget(feature_container)

        # Tip and Customize row
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)

        self.tip_label = QLabel("Tip: Press Ctrl + I to activate Prompt Anywhere.")
        self.tip_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.tip_label.setStyleSheet(self.tip_label_stylesheet())
        bottom_layout.addWidget(self.tip_label)

        self.font_down_btn = QPushButton("-")
        self.font_down_btn.setFixedSize(18, 18)
        self.font_down_btn.setStyleSheet(self.font_button_stylesheet())
        self.font_down_btn.clicked.connect(lambda: self.adjust_font_scale(-1))
        bottom_layout.addWidget(self.font_down_btn)

        self.font_up_btn = QPushButton("+")
        self.font_up_btn.setFixedSize(18, 18)
        self.font_up_btn.setStyleSheet(self.font_button_stylesheet())
        self.font_up_btn.clicked.connect(lambda: self.adjust_font_scale(1))
        bottom_layout.addWidget(self.font_up_btn)

        self.customize_btn = QPushButton("+ Customize")
        self.customize_btn.setFixedHeight(18)
        self.customize_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.customize_btn.setStyleSheet(self.customize_button_stylesheet())
        self.customize_btn.clicked.connect(lambda: self.trigger_feature("customize"))
        bottom_layout.addWidget(self.customize_btn)

        container_layout.addLayout(bottom_layout)

        self.content_widget.setLayout(container_layout)

        if self._show_chrome:
            container_stack = QStackedLayout()
            container_stack.setContentsMargins(0, 0, 0, 0)
            container_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
            container_stack.addWidget(self.background_label)
            container_stack.addWidget(self.content_widget)
            self.container.setLayout(container_stack)
            layout.addWidget(self.container)
        else:
            layout.addWidget(self.content_widget)
        self.setLayout(layout)
        self.apply_font_scale()
        self.resize_to_contents()
        if self._show_chrome:
            self.update_background_pixmap()

        # Focus input field
        self.input_field.setFocus()

    def create_utility_button(self, text: str, icon: str) -> QPushButton:
        """Create small utility button that fits text"""
        btn = QPushButton(text)
        btn.setFixedHeight(16)
        btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(self.utility_button_stylesheet())
        icon_name = self.get_icon_name(icon)
        if icon_name:
            self.set_button_icon(btn, icon_name, self.scaled_icon_size(12))
            self.utility_button_icons.append((btn, icon_name))
        self.utility_buttons.append(btn)
        return btn

    def create_feature_button(self, name: str, hotkey: str, icon: str) -> QPushButton:
        """Create feature button with name and outlined hotkey"""
        from PySide6.QtWidgets import QVBoxLayout, QLabel

        # Create button with custom layout
        btn = QPushButton()
        btn.setFixedHeight(46)
        btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # Create internal layout
        layout = QVBoxLayout(btn)
        layout.setContentsMargins(3, 4, 3, 4)
        layout.setSpacing(2)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        icon_name = self.get_icon_name(icon)
        if icon_name:
            icon_label.setPixmap(self.load_icon_pixmap(icon_name, self.scaled_icon_size(14)))
            self.feature_icon_labels.append((icon_label, icon_name))
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)
        top_row.addWidget(icon_label)

        # Feature name
        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        name_label.setStyleSheet(self.feature_name_stylesheet())
        top_row.addWidget(name_label)
        top_row.addStretch()
        layout.addLayout(top_row)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.12);
                border: none;
            }
        """)
        layout.addWidget(separator)

        # Hotkey with outline
        hotkey_label = QLabel(hotkey)
        hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_label.setStyleSheet(self.feature_hotkey_stylesheet())
        layout.addWidget(hotkey_label)

        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 30, 50, 180);
                border: 1px solid rgba(255, 157, 92, 0.3);
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(60, 40, 70, 200);
                border: 1px solid rgba(255, 157, 92, 0.5);
            }
            QPushButton:pressed {
                background-color: rgba(30, 20, 40, 180);
            }
        """)
        self.feature_buttons.append(btn)
        self.feature_name_labels.append(name_label)
        self.feature_hotkey_labels.append(hotkey_label)
        return btn

    def apply_blur_effect(self):
        """Apply Windows blur effect"""
        if sys.platform == 'win32':
            hwnd = int(self.winId())
            apply_blur_effect(hwnd)

    def get_background_path(self) -> str:
        """Return the background image path."""
        return str(Path(__file__).resolve().parents[1] / "assets" / "background.png")

    def update_background_pixmap(self):
        """Scale and apply the background image to the container."""
        if not self._show_chrome:
            return
        if self.background_pixmap.isNull():
            return
        target_size = self.container.size()
        source = self.background_pixmap
        if source.width() < target_size.width() or source.height() < target_size.height():
            source = source.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
        x = max(0, (source.width() - target_size.width()) // 2)
        y = max(0, (source.height() - target_size.height()) // 2)
        cropped = source.copy(x, y, target_size.width(), target_size.height())
        self.background_label.setPixmap(cropped)
        self.background_label.resize(target_size)

    def scaled_pt(self, base_size: int) -> int:
        """Return scaled font size in points."""
        return max(6, base_size + self.font_scale)

    def scaled_height(self, base_height: int) -> int:
        """Return scaled widget height."""
        return max(12, base_height + (self.font_scale * 2))

    def scaled_icon_size(self, base_size: int) -> int:
        """Return scaled icon size."""
        return max(10, base_size + (self.font_scale * 2))

    def get_asset_path(self, filename: str) -> str:
        """Return the full path to an asset file."""
        return str(Path(__file__).resolve().parents[1] / "assets" / filename)

    def load_icon_pixmap(self, filename: str, size: int) -> QPixmap:
        """Load an icon pixmap from assets."""
        path = self.get_asset_path(filename)
        icon = QIcon(path)
        if icon.isNull():
            return QPixmap()
        return icon.pixmap(size, size)

    def set_button_icon(self, button: QPushButton, filename: str, size: int):
        """Apply an icon from assets to a button."""
        path = self.get_asset_path(filename)
        icon = QIcon(path)
        if icon.isNull():
            return
        button.setIcon(icon)
        button.setIconSize(QSize(size, size))

    def get_icon_name(self, icon_key: str) -> str:
        """Map logical icon keys to asset filenames."""
        icon_map = {
            "screenshot": "image_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
            "history": "history_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
            "grid": "widget_small_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
            "settings": "menu_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
            "google": "google.svg",
            "files": "search_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
            "browser": "browse_gallery_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
            "terminal": "prompt_suggestion_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
            "maximize": "toggle_on_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
            "send": "send_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
            "close": "close_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg",
        }
        return icon_map.get(icon_key, "")

    def title_label_stylesheet(self) -> str:
        return f"""
            QLabel {{
                color: #FF9D5C;
                font-family: 'Segoe UI', sans-serif;
                font-size: {self.scaled_pt(12)}pt;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """

    def close_button_stylesheet(self) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: rgba(255, 255, 255, 0.6);
                border: none;
                font-size: {self.scaled_pt(12)}pt;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: rgba(255, 255, 255, 1.0);
            }}
        """

    def input_stylesheet(self) -> str:
        return f"""
            QLineEdit {{
                background-color: rgba(30, 30, 30, 200);
                color: #FFFFFF;
                border: 1px solid rgba(255, 157, 92, 0.3);
                border-radius: 6px;
                padding: 0px 8px;
                font-family: 'Segoe UI', sans-serif;
                font-size: {self.scaled_pt(10)}pt;
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(255, 157, 92, 0.6);
            }}
        """

    def send_button_stylesheet(self) -> str:
        return f"""
            QPushButton {{
                background-color: rgba(255, 157, 92, 220);
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0px;
                font-family: 'Segoe UI', sans-serif;
                font-size: {self.scaled_pt(8)}pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 177, 112, 240);
            }}
            QPushButton:pressed {{
                background-color: rgba(235, 137, 72, 200);
            }}
        """

    def utility_button_stylesheet(self) -> str:
        return f"""
            QPushButton {{
                background-color: rgba(50, 50, 50, 150);
                color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                font-size: {self.scaled_pt(7)}pt;
                padding: 1px 5px;
            }}
            QPushButton:hover {{
                background-color: rgba(70, 70, 70, 180);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}
        """

    def feature_name_stylesheet(self) -> str:
        return f"""
            QLabel {{
                color: #FFFFFF;
                font-family: 'Segoe UI', sans-serif;
                font-size: {self.scaled_pt(7)}pt;
                background: transparent;
                border: none;
            }}
        """

    def feature_hotkey_stylesheet(self) -> str:
        return f"""
            QLabel {{
                color: rgba(255, 157, 92, 0.9);
                font-family: 'Segoe UI', sans-serif;
                font-size: {self.scaled_pt(6)}pt;
                background: transparent;
                border: 1px solid rgba(255, 157, 92, 0.4);
                border-radius: 3px;
                padding: 0px 3px;
            }}
        """

    def tip_label_stylesheet(self) -> str:
        return f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.5);
                font-family: 'Segoe UI', sans-serif;
                font-size: {self.scaled_pt(6)}pt;
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """

    def customize_button_stylesheet(self) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: rgba(255, 157, 92, 220);
                border: 1px solid rgba(255, 157, 92, 0.3);
                border-radius: 4px;
                padding: 0px 8px;
                font-family: 'Segoe UI', sans-serif;
                font-size: {self.scaled_pt(7)}pt;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 157, 92, 0.1);
                border: 1px solid rgba(255, 157, 92, 0.5);
            }}
        """

    def font_button_stylesheet(self) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                font-family: 'Segoe UI', sans-serif;
                font-size: {self.scaled_pt(7)}pt;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.35);
            }}
        """

    def adjust_font_scale(self, delta: int):
        """Adjust font scale within allowed range."""
        self.font_scale = max(self.min_font_scale, min(self.max_font_scale, self.font_scale + delta))
        self.apply_font_scale()
        self.resize_to_contents()

    def apply_font_scale(self):
        """Apply the current font scale to all widgets."""
        if self._show_chrome:
            self.title_label.setStyleSheet(self.title_label_stylesheet())
            self.close_btn.setStyleSheet(self.close_button_stylesheet())
            self.close_btn.setFixedSize(self.scaled_height(20), self.scaled_height(20))
            self.set_button_icon(self.close_btn, self.get_icon_name("close"), self.scaled_icon_size(12))
            self.close_btn.setText("")

        self.input_field.setStyleSheet(self.input_stylesheet())
        self.input_field.setFixedHeight(self.scaled_height(32))

        self.send_btn.setStyleSheet(self.send_button_stylesheet())
        self.send_btn.setFixedHeight(self.scaled_height(32))
        self.set_button_icon(self.send_btn, self.get_icon_name("send"), self.scaled_icon_size(12))

        for btn in self.utility_buttons:
            btn.setStyleSheet(self.utility_button_stylesheet())
            btn.setFixedHeight(self.scaled_height(16))

        for btn, icon_name in self.utility_button_icons:
            self.set_button_icon(btn, icon_name, self.scaled_icon_size(12))

        for btn in self.feature_buttons:
            btn.setFixedHeight(self.scaled_height(46))

        for label in self.feature_name_labels:
            label.setStyleSheet(self.feature_name_stylesheet())

        for label in self.feature_hotkey_labels:
            label.setStyleSheet(self.feature_hotkey_stylesheet())

        for label, icon_name in self.feature_icon_labels:
            label.setPixmap(self.load_icon_pixmap(icon_name, self.scaled_icon_size(14)))

        self.tip_label.setStyleSheet(self.tip_label_stylesheet())
        self.customize_btn.setStyleSheet(self.customize_button_stylesheet())
        self.customize_btn.setFixedHeight(self.scaled_height(18))

        self.font_down_btn.setStyleSheet(self.font_button_stylesheet())
        self.font_up_btn.setStyleSheet(self.font_button_stylesheet())
        self.font_down_btn.setFixedSize(self.scaled_height(18), self.scaled_height(18))
        self.font_up_btn.setFixedSize(self.scaled_height(18), self.scaled_height(18))

    def resize_to_contents(self):
        """Resize window to match current UI content size."""
        self.adjustSize()
        current_size = self.size()
        target_width = max(current_size.width(), self.min_window_size.width())
        target_height = max(current_size.height(), self.min_window_size.height())
        self.resize(target_width, target_height)
        if not self._embedded:
            self.center_on_screen()
        if self._show_chrome:
            self.update_background_pixmap()
        if not self._embedded and self._show_chrome:
            self.update_window_mask()

    def resizeEvent(self, event):
        """Keep rounded window mask in sync with size."""
        super().resizeEvent(event)
        if self._show_chrome:
            self.update_background_pixmap()
        if not self._embedded and self._show_chrome:
            self.update_window_mask()

    def update_window_mask(self):
        """Apply rounded corner mask to remove square edges."""
        if not self._show_chrome:
            return
        from PySide6.QtGui import QPainterPath, QRegion
        radius = 16
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

    def capture_screenshot(self):
        """Open screenshot overlay"""
        window_to_hide = self.window() if self._embedded else self
        window_to_hide.hide()
        self.screenshot_overlay = ScreenshotOverlay()
        self.screenshot_overlay.screenshot_taken.connect(self.on_screenshot_captured)
        self.screenshot_overlay.show()

    @Slot(bytes)
    def on_screenshot_captured(self, image_bytes):
        """Handle captured screenshot"""
        self.screenshot_bytes = image_bytes
        self.screenshot_overlay = None
        window_to_show = self.window() if self._embedded else self
        window_to_show.show()
        self.input_field.setFocus()

    def submit_prompt(self):
        """Submit prompt with optional screenshot"""
        prompt = self.input_field.text().strip()
        if not prompt:
            return

        self.prompt_submitted.emit(prompt, self.screenshot_bytes)
        # In embedded mode, the shell owns visibility.
        if not self._embedded:
            self.close()
        else:
            self.input_field.clear()

    def trigger_feature(self, feature_name: str):
        """Trigger a feature with current prompt"""
        prompt = self.input_field.text().strip()
        self.feature_triggered.emit(feature_name, prompt)
        # Don't close the window for features, let them execute

    def mousePressEvent(self, event):
        """Enable window dragging (top-level only)."""
        if self._embedded:
            return super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        """Handle window dragging (top-level only)."""
        if self._embedded:
            return super().mouseMoveEvent(event)
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)

    def keyPressEvent(self, event):
        """ESC behavior.

        - Embedded: let the shell handle ESC.
        - Top-level: close the window.
        """
        if event.key() == Qt.Key.Key_Escape:
            if not self._embedded:
                self.close()
            event.accept()
            return
        super().keyPressEvent(event)
