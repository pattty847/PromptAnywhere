"""Asset path and icon helpers for UI."""

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QPushButton


def _assets_dir() -> Path:
    """Return the ui/assets directory."""
    return Path(__file__).resolve().parent.parent / "assets"


def get_asset_path(filename: str) -> str:
    """Return the full path to an asset file."""
    return str(_assets_dir() / filename)


def set_button_icon(button: QPushButton, filename: str, size: int) -> None:
    """Apply an icon from assets to a button."""
    path = get_asset_path(filename)
    icon = QIcon(path)
    if icon.isNull():
        return
    button.setIcon(icon)
    button.setIconSize(QSize(size, size))


def load_icon_pixmap(filename: str, size: int) -> QPixmap:
    """Load an icon pixmap from assets."""
    path = get_asset_path(filename)
    icon = QIcon(path)
    if icon.isNull():
        return QPixmap()
    return icon.pixmap(size, size)


# Logical icon keys to asset filenames (used by main prompt window and others)
ICON_MAP = {
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


def get_icon_name(icon_key: str) -> str:
    """Map logical icon keys to asset filenames."""
    return ICON_MAP.get(icon_key, "")
