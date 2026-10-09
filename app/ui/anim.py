"""过渡动画原语。

为什么这里没有一行 CSS：QSS 只是 CSS2.1 的一个子集，**不支持** transition /
animation / @keyframes / transform（也不支持 box-shadow，所以投影另见 effects.py）。
QSS 里所有伪状态（:hover、[active="true"]）的切换都是瞬时硬跳，观感就是「顿」。
想做过渡只有一条路：用 Qt 自己的动画框架算中间值。

三条硬规矩（动这个文件之前先读）：

1. **绝不逐帧拼 QSS 字符串做动画**。每帧 setStyleSheet 都会触发一次全量样式重算，
   帧率会直接塌掉。颜色过渡必须走自绘（见 paint_tint_frame）或 graphics effect。
2. **一个控件同时只能挂一个 QGraphicsEffect**：挂了投影就不能再挂透明度，反之亦然。
   所以透明度只用在没挂阴影的控件上（如状态文字）。
3. **动画一律短、一律 OutCubic、只在状态变化的瞬间播**。界面静止时不该有任何东西在动；
   弹跳、缩放、发光那套会让工具软件显得廉价。
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

DURATION_FLASH = 150  # 文字、反馈类：快到几乎察觉不到，只是不再「啪」地跳
DURATION_SLIDE = 200  # 数值滚动、颜色过渡
DURATION_FADE = 220  # 页面级淡入


def mix(start: str, end: str, t: float) -> QColor:
    """在两个十六进制颜色之间线性插值（t=0 取 start，t=1 取 end）。"""
    low, high = QColor(start), QColor(end)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return QColor(
        round(low.red() + (high.red() - low.red()) * t),
        round(low.green() + (high.green() - low.green()) * t),
        round(low.blue() + (high.blue() - low.blue()) * t),
    )


class TintAnimation(QObject):
    """一个 0→1 的过渡进度，供控件在 paintEvent 里插值颜色。

    自绘控件（拖拽条 / 拖拽区）用它替代 QSS 的 [active="true"] 硬切：
    进度变化时发 changed，控件只需 update()，颜色由 paint_tint_frame 插出来。
    """

    changed = Signal(float)

    def __init__(self, parent: QObject | None = None, duration: int = DURATION_SLIDE):
        super().__init__(parent)
        self._value = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._apply)

    @property
    def value(self) -> float:
        return self._value

    def _apply(self, value: object) -> None:
        self._value = float(value)
        self.changed.emit(self._value)

    def to(self, target: float) -> None:
        """过渡到目标值；已在目标上则不动（避免重复触发重绘）。"""
        target = 1.0 if target >= 0.5 else 0.0
        if abs(target - self._value) < 1e-4:
            return
        self._anim.stop()
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(target)
        self._anim.start()

    def snap(self, target: float) -> None:
        """立刻到位（初始状态用，不要有动画）。"""
        self._anim.stop()
        self._apply(1.0 if target >= 0.5 else 0.0)


class ValueRoller(QObject):
    """把「值跳变」变成「数值滚动」，用于 QProgressBar 这类 int 属性。

    进度条原来直接 setValue(done)，是格子一格一格地蹦；改成滚动后是滑过去的。
    时长比单张图的处理耗时短（200ms），所以不会出现「进度条追不上真实进度」。
    """

    def __init__(
        self,
        target: QObject,
        name: str,
        parent: QObject | None = None,
        duration: int = DURATION_SLIDE,
    ):
        super().__init__(parent)
        self._target = target
        self._name = name
        self._anim = QPropertyAnimation(target, name.encode("ascii"), self)
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def roll_to(self, value: int) -> None:
        """滚到目标值。起点取属性当前值，所以连续调用不会回跳。"""
        self._anim.stop()
        self._anim.setEndValue(int(value))
        self._anim.start()

    def snap(self, value: int) -> None:
        """立刻到位并停表。

        完成时必须用这个：否则进度条还差最后一格，在窗口里慢慢地爬，
        和「已完成」的状态文字对不上。
        """
        self._anim.stop()
        self._target.setProperty(self._name, int(value))

    def stop(self) -> None:
        self._anim.stop()


def paint_tint_frame(
    widget: QWidget,
    *,
    tint: float,
    radius: int,
    idle_bg: str,
    active_bg: str,
    idle_border: str,
    active_border: str,
    idle_top: str,
    active_top: str,
) -> None:
    """自绘一块会随 tint 过渡的表面：底色 + 1px 边框 + 顶部 1px 高光。

    tint=0 用 idle_* 那一套，tint=1 用 active_* 那一套，中间线性插值。
    调用方的 paintEvent 里直接调它、不要再去调 super().paintEvent()，
    否则 QSS 的背景会和自己画的叠在一起。
    """
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.Antialiasing, True)

    # 内缩半像素：1px 的线画在像素中心才不会被抗锯齿糊成两像素。
    # 必须用 QRectF——QRect.adjusted() 只吃 int，传 0.5 会被截断成 0，
    # 线就正好卡在像素边界上，两侧各糊一半。
    rect = QRectF(widget.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

    painter.setPen(Qt.NoPen)
    painter.setBrush(mix(idle_bg, active_bg, tint))
    painter.drawRoundedRect(rect, radius, radius)

    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(mix(idle_border, active_border, tint), 1.0))
    painter.drawRoundedRect(rect, radius, radius)

    # 顶部 1px 高光（QSS 里用 border-top-color 做的那条，自绘得自己补）
    clip = QPainterPath()
    clip.addRoundedRect(rect, radius, radius)
    painter.setClipPath(clip)
    painter.setPen(QPen(mix(idle_top, active_top, tint), 1.0))
    painter.drawLine(
        QPointF(rect.left(), rect.top()), QPointF(rect.right(), rect.top())
    )
    painter.end()


def fade_in(widget: QWidget, duration: int = DURATION_FLASH, start: float = 0.4):
    """让控件淡入一次，返回常驻的动画对象（调用方持有并复用）。

    start 不给 0：从全透明开始会「闪一下」，从 0.4 开始只是柔和地提亮。
    注意会占用该控件唯一的 graphics effect 槽位——挂了阴影的控件不能用。
    """
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(1.0)

    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.setStartValue(start)
    animation.setEndValue(1.0)
    return animation
