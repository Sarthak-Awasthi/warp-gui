"""Runtime-generated icons so the app needs no external image assets.

Each icon is a filled disc (colour encodes the connection state) with a white
Cloudflare-style cloud drawn on top. Rendered with QPainter at request time and
cached per (state, size).
"""

from __future__ import annotations

from functools import lru_cache

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap

STATE_COLORS = {
    "connected": "#f6821f",    # Cloudflare orange
    "connecting": "#fbad41",   # amber
    "disconnected": "#8a8f98",  # grey
    "error": "#e5484d",        # red
}


def _cloud(painter: QPainter, size: int) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#ffffff"))
    s = size
    # A few overlapping ellipses plus a rounded base form the cloud.
    painter.drawEllipse(QRectF(s * 0.22, s * 0.44, s * 0.28, s * 0.28))
    painter.drawEllipse(QRectF(s * 0.40, s * 0.34, s * 0.34, s * 0.34))
    painter.drawEllipse(QRectF(s * 0.56, s * 0.46, s * 0.24, s * 0.24))
    painter.drawRoundedRect(
        QRectF(s * 0.26, s * 0.52, s * 0.50, s * 0.16), s * 0.08, s * 0.08
    )


@lru_cache(maxsize=None)
def state_pixmap(state: str, size: int) -> QPixmap:
    color = QColor(STATE_COLORS.get(state, STATE_COLORS["disconnected"]))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    inset = size * 0.03
    p.drawEllipse(QRectF(inset, inset, size - 2 * inset, size - 2 * inset))
    _cloud(p, size)
    p.end()
    return pm


@lru_cache(maxsize=None)
def state_icon(state: str, size: int = 128) -> QIcon:
    return QIcon(state_pixmap(state, size))
