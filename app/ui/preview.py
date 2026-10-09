"""原图与结果的对比预览。

中间的分割线可以拖动：左边是原图，右边是处理结果。透明区域用棋盘格渲染，
否则 PNG 的透明部分在暗色界面上会变成一片黑，分不清是"透明"还是"没抠出来"。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import style

CHECKER_SIZE = 10


def pil_to_qimage(img: Image.Image) -> QImage:
    """PIL -> QImage。必须 copy()，否则底层 buffer 被回收后画面会花。"""
    rgba = img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
    return qimage.copy()


def load_qimage(path: Path) -> QImage | None:
    try:
        with Image.open(path) as img:
            from PIL import ImageOps

            return pil_to_qimage(ImageOps.exif_transpose(img))
    except Exception:  # noqa: BLE001 - 预览失败不该影响主流程
        return None


class CompareView(QWidget):
    """左右分割对比控件。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._before: QImage | None = None
        self._after: QImage | None = None
        self._split = 0.5
        self._dragging = False
        self.setMinimumSize(520, 380)
        self.setMouseTracking(True)

    def set_images(self, before: QImage | None, after: QImage | None) -> None:
        self._before = before
        self._after = after
        self.update()

    def _image_rect(self) -> QRect:
        """按等比缩放计算图像在控件内的显示矩形（居中）。"""
        source = self._before if self._before is not None else self._after
        if source is None:
            return QRect()

        area = self.rect().adjusted(12, 12, -12, -12)
        if area.width() <= 0 or area.height() <= 0:
            return QRect()

        scale = min(area.width() / source.width(), area.height() / source.height())
        width = max(1, int(source.width() * scale))
        height = max(1, int(source.height() * scale))
        left = area.left() + (area.width() - width) // 2
        top = area.top() + (area.height() - height) // 2
        return QRect(left, top, width, height)

    def _draw_checkerboard(self, painter: QPainter, rect: QRect) -> None:
        painter.save()
        painter.setClipRect(rect)
        painter.fillRect(rect, QColor(style.CHECKER_DARK))
        rows = rect.height() // CHECKER_SIZE + 2
        cols = rect.width() // CHECKER_SIZE + 2
        for row in range(rows):
            for col in range(cols):
                if (row + col) % 2 == 0:
                    continue
                painter.fillRect(
                    rect.left() + col * CHECKER_SIZE,
                    rect.top() + row * CHECKER_SIZE,
                    CHECKER_SIZE,
                    CHECKER_SIZE,
                    QColor(style.CHECKER_LIGHT),
                )
        painter.restore()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor(style.PREVIEW_BG))

        target = self._image_rect()
        if target.isNull():
            painter.setPen(QPen(QColor(style.TEXT_FAINT)))
            painter.drawText(self.rect(), Qt.AlignCenter, "双击任务列表中的图片以查看对比")
            return

        self._draw_checkerboard(painter, target)

        split_x = target.left() + int(target.width() * self._split)

        # 左半：原图
        if self._before is not None:
            painter.save()
            painter.setClipRect(QRect(target.left(), target.top(), split_x - target.left(), target.height()))
            painter.drawImage(target, self._before)
            painter.restore()

        # 右半：结果（未处理时显示原图并提示）
        painter.save()
        painter.setClipRect(QRect(split_x, target.top(), target.right() - split_x + 1, target.height()))
        if self._after is not None:
            painter.drawImage(target, self._after)
        elif self._before is not None:
            painter.drawImage(target, self._before)
            painter.fillRect(
                QRect(split_x, target.top(), target.right() - split_x + 1, target.height()),
                QColor(255, 255, 255, 170),
            )
        painter.restore()

        if self._after is None:
            painter.setPen(QPen(QColor(style.TEXT_DIM)))
            painter.drawText(
                QRect(split_x, target.top(), target.right() - split_x, target.height()),
                Qt.AlignCenter,
                "尚未处理",
            )

        # 分割线
        painter.setPen(QPen(QColor(style.ACCENT), 2))
        painter.drawLine(split_x, target.top(), split_x, target.bottom())

        # 两个角标
        painter.setPen(QPen(QColor(style.TEXT)))
        painter.fillRect(target.left() + 8, target.top() + 8, 44, 20, QColor(0, 0, 0, 160))
        painter.drawText(target.left() + 8, target.top() + 8, 44, 20, Qt.AlignCenter, "原图")
        if self._after is not None:
            painter.fillRect(target.right() - 52, target.top() + 8, 44, 20, QColor(0, 0, 0, 160))
            painter.drawText(target.right() - 52, target.top() + 8, 44, 20, Qt.AlignCenter, "结果")

    # ---------- 拖动分割线 ----------
    def _hit_divider(self, pos: QPoint) -> bool:
        target = self._image_rect()
        if target.isNull() or self._after is None:
            return False
        split_x = target.left() + int(target.width() * self._split)
        return abs(pos.x() - split_x) <= 6

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and (
            self._hit_divider(event.position().toPoint()) or self._after is not None
        ):
            self._dragging = True
            self._update_split(event.position().toPoint())
            self.setCursor(Qt.SizeHorCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._dragging:
            self._update_split(pos)
        elif self._hit_divider(pos):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._dragging = False
        self.setCursor(Qt.ArrowCursor)

    def _update_split(self, pos: QPoint) -> None:
        target = self._image_rect()
        if target.isNull() or target.width() == 0:
            return
        ratio = (pos.x() - target.left()) / target.width()
        self._split = min(1.0, max(0.0, ratio))
        self.update()


class PreviewWindow(QDialog):
    """对比预览窗口。"""

    def __init__(self, src: Path, dst: Path | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"对比预览 - {src.name}")
        self.resize(960, 680)
        self.setStyleSheet(style.STYLE)

        self.view = CompareView(self)
        self.view.set_images(load_qimage(src), load_qimage(dst) if dst else None)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.view, 1)

        info = QHBoxLayout()
        info.setSpacing(14)
        source_label = QLabel(f"原图：{src}")
        source_label.setProperty("role", "hint")
        source_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info.addWidget(source_label, 1)

        if dst is None:
            result_text = "结果：尚未生成"
        else:
            exists = dst.exists()
            result_text = f"结果：{dst}" if exists else f"结果：{dst}（文件不存在）"
        result_label = QLabel(result_text)
        result_label.setProperty("role", "hint")
        result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info.addWidget(result_label, 1)

        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        info.addWidget(close_button)
        layout.addLayout(info)
