"""Shared background label and pixmap scaling."""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


class FixedBackgroundLabel(QLabel):
    """Background label that does not affect layout sizing."""

    def sizeHint(self):
        return QSize(0, 0)


def update_background_pixmap(
    background_label: QLabel,
    background_pixmap: QPixmap,
    target_size: QSize,
) -> None:
    """Scale and apply the background image to the label (crop to target size)."""
    if background_pixmap.isNull():
        return
    source = background_pixmap
    if source.width() < target_size.width() or source.height() < target_size.height():
        source = source.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
    x = max(0, (source.width() - target_size.width()) // 2)
    y = max(0, (source.height() - target_size.height()) // 2)
    cropped = source.copy(x, y, target_size.width(), target_size.height())
    background_label.setPixmap(cropped)
    background_label.resize(target_size)
