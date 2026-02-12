"""Window shape utilities (rounded mask, etc.)."""

from PySide6.QtGui import QPainterPath, QRegion
from PySide6.QtWidgets import QWidget


def apply_rounded_mask(widget: QWidget, radius: int = 16) -> None:
    """Apply a rounded corner mask to remove square edges."""
    rect = widget.rect()
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    region = QRegion(path.toFillPolygon().toPolygon())
    widget.setMask(region)
