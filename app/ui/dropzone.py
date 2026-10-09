"""空状态拖拽区：列表为空时，整块内容区就是投放目标。

它和任务表格共用同一块区域（见 main_window 的 center_stack）：没有输入时
顶替表格，一旦拖入/加入图片就让位给列表，同时列表上方保留一根 44px 的
提示条，让「随时可以继续拖入」始终可见。

拖放事件统一由主窗口处理（这里 setAcceptDrops(False)，事件自动冒泡上去），
组件只负责显示，以及把「选择图片…」的点击转发给主窗口。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import style

GLYPH = 60
DEFAULT_TITLE = "把图片或文件夹拖到这里"
DEFAULT_HINT = "支持 PNG / JPG / WebP / BMP / TIFF · 可一次拖入整个文件夹"


def _glyph() -> QPixmap:
    """自绘一个相框图标（圆角框 + 太阳 + 山），免得再添二进制资源。"""
    pixmap = QPixmap(GLYPH, GLYPH)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)

    pen = QPen(QColor(style.ACCENT))
    pen.setWidthF(2.4)
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    frame = QRectF(6, 12, GLYPH - 12, GLYPH - 24)
    painter.drawRoundedRect(frame, 6, 6)
    painter.drawEllipse(QRectF(frame.left() + 8, frame.top() + 7, 7, 7))

    bottom = frame.bottom() - 1
    hill = QPainterPath()
    hill.moveTo(frame.left() + 3, bottom)
    hill.lineTo(frame.left() + 17, bottom - 13)
    hill.lineTo(frame.left() + 26, bottom - 4)
    hill.lineTo(frame.left() + 32, bottom - 9)
    hill.lineTo(frame.right() - 3, bottom)
    painter.drawPath(hill)
    painter.end()
    return pixmap


class DropArea(QFrame):
    """空状态下的整块投放区：图标 + 标题 + 说明 + 「选择图片…」。"""

    pick_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "droparea")
        self.setAcceptDrops(False)

        column = QVBoxLayout(self)
        column.setContentsMargins(24, 24, 24, 24)
        column.setSpacing(0)
        column.addStretch(1)

        glyph = QLabel()
        glyph.setPixmap(_glyph())
        glyph.setAlignment(Qt.AlignCenter)
        column.addWidget(glyph)

        column.addSpacing(16)
        self.title_label = QLabel(DEFAULT_TITLE)
        self.title_label.setProperty("role", "droptitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        column.addWidget(self.title_label)

        column.addSpacing(7)
        self.hint_label = QLabel(DEFAULT_HINT)
        self.hint_label.setProperty("role", "hint")
        self.hint_label.setAlignment(Qt.AlignCenter)
        column.addWidget(self.hint_label)

        column.addSpacing(20)
        row = QHBoxLayout()
        row.addStretch(1)
        self.pick_button = QPushButton("选择图片…")
        self.pick_button.setProperty("role", "primary")
        self.pick_button.setMinimumWidth(120)
        self.pick_button.clicked.connect(self.pick_requested)
        row.addWidget(self.pick_button)
        row.addStretch(1)
        column.addLayout(row)

        column.addStretch(1)

    def set_active(self, active: bool) -> None:
        """拖拽悬停时整块区域加重描边。"""
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_message(self, title: str, hint: str) -> None:
        self.title_label.setText(title)
        self.hint_label.setText(hint)
