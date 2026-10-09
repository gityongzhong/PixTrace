"""投影（QSS 画不出 box-shadow，只能靠 QGraphicsEffect 补）。

尺度约定：
- 卡片级（设置面板 / 底部条 / 空状态拖拽区）：半径小、偏移小。
  原因是 QGraphicsEffect 的合成结果会被父控件矩形裁剪，半径给大了只会被切边，
  看起来像脏边。10px 半径 + 3px 下移在 8px 的布局间距里刚好露出。
- 弹出层（QMenu 这类顶层 widget）：不受父级裁剪，可以给到 20px 左右，
  这是「菜单浮起来」观感的主要来源。

注意：挂上 effect 后，控件与其所有子控件会被整体渲染到离屏图再合成。
进度条这类高频刷新的子控件会有额外开销，所以只用在静态容器上，不要挂在树上。
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget


def add_shadow(
    widget: QWidget,
    radius: int = 10,
    dy: int = 3,
    dx: int = 0,
    alpha: int = 110,
) -> QGraphicsDropShadowEffect:
    """给控件挂一层投影，返回 effect 以便调用方调整。"""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(radius)
    effect.setOffset(dx, dy)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)
    return effect


def add_card_shadow(widget: QWidget, radius: int = 9, dy: int = 2):
    """卡片级投影：面板、底部条、空状态拖拽区。

    alpha 压到 65：暗色底下 100 以上的黑投影会在卡片四周糊出一圈明显的黑边，
    反而显得脏。投影只需要一层存在感很弱的过渡。
    """
    return add_shadow(widget, radius=radius, dy=dy, alpha=65)


def add_popup_shadow(widget: QWidget):
    """弹出层投影：菜单、下拉列表。"""
    return add_shadow(widget, radius=20, dy=5, alpha=110)
