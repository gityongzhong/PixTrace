"""设置面板：界面上唯一的参数区——背景（透明 / 纯色）+ 保存位置。

产品定位就是两个动作——去掉背景、换成纯色背景，所以模型档位、输出格式、
并发数、羽化半径这些工程参数一律不出现在界面上，而是固定策略：

- 模型：高精档 isnet（发丝与复杂边缘明显更好，单张约 1.2 秒）
- 格式：PNG（无损、保留透明通道；纯色底同样用 PNG，便于再次编辑）
- 并发：由模型档位自己决定（实测大模型单进程多线程吞吐最优）
- 覆盖：同名输出直接覆盖更新，让「点开始 = 拿到最新结果」

这些策略都写在 build_options() 里，想改只需改这一处。

本面板只管参数：状态文字、进度条与执行按钮在主窗口的独立动作行里
（挤在这一行行尾会把「保存到」压得没地方，也不符合「先选参数再动手」的顺序）。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import DEFAULT_MODEL_KEY
from ..core.types import BackgroundKind, BackgroundSpec, JobOptions, OutputFormat
from . import effects, style

DEFAULT_BG_COLOR = (255, 255, 255)
DEST_ALONGSIDE = "alongside"
DEST_CUSTOM = "custom"


class SettingsPanel(QFrame):
    """背景 + 保存位置。字段名保持稳定，供配置持久化与测试脚本使用。"""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "panel")
        self._color: tuple[int, int, int] = DEFAULT_BG_COLOR
        self._dest_mode: str = DEST_ALONGSIDE
        self._custom_dir: Path | None = None
        self._build()
        self._connect()
        self._sync_enabled()
        self._refresh_dest()

    # ------------------------------------------------------------ 构建
    def _build(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 9, 12, 9)
        row.setSpacing(10)

        label = QLabel("背景")
        row.addWidget(label)

        self.bg_transparent = QRadioButton("透明")
        self.bg_transparent.setToolTip("去掉背景，输出带透明通道的 PNG")
        row.addWidget(self.bg_transparent)

        self.bg_color = QRadioButton("纯色")
        self.bg_color.setToolTip("去掉背景后填充为指定颜色")
        row.addWidget(self.bg_color)

        self.color_button = QPushButton()
        self.color_button.setProperty("role", "swatch")
        self.color_button.setFixedSize(72, 24)
        self.color_button.setToolTip("点击选择背景颜色")
        row.addWidget(self.color_button)

        row.addSpacing(4)
        row.addWidget(self._separator())
        row.addSpacing(4)

        self.dest_button = QPushButton()
        self.dest_button.setCursor(Qt.PointingHandCursor)
        self.dest_button.setToolTip("结果保存到哪里")
        row.addWidget(self.dest_button)

        row.addStretch(1)
        self._apply_color_style()

    def _separator(self) -> QWidget:
        line = QFrame()
        line.setProperty("role", "separator")
        line.setFixedSize(1, 18)
        return line

    # ------------------------------------------------------------ 交互
    def _connect(self) -> None:
        self.bg_transparent.toggled.connect(self._on_bg_toggled)
        self.bg_color.toggled.connect(self._on_bg_toggled)
        self.color_button.clicked.connect(self._pick_color)
        self.dest_button.clicked.connect(self._show_dest_menu)

    def _on_bg_toggled(self) -> None:
        self._sync_enabled()
        self.changed.emit()

    def _sync_enabled(self) -> None:
        self.color_button.setEnabled(self.bg_color.isChecked())
        self._apply_color_style()

    def _apply_color_style(self) -> None:
        red, green, blue = self._color
        if not self.color_button.isEnabled():
            # 禁用时向面板底色混合，否则内联样式会让它看起来仍可点击
            panel = style.rgb(style.BG_PANEL)
            blend = 0.35
            red = int(panel[0] + (red - panel[0]) * blend)
            green = int(panel[1] + (green - panel[1]) * blend)
            blue = int(panel[2] + (blue - panel[2]) * blend)
            text = style.TEXT_FAINT
        else:
            luma = red * 0.299 + green * 0.587 + blue * 0.114
            text = "#000000" if luma > 140 else "#ffffff"
        self.color_button.setStyleSheet(
            f"background-color: rgb({red},{green},{blue}); color: {text};"
            f" border: 1px solid {style.BORDER_STRONG}; border-radius: 4px;"
            f" font-size: 12px;"
        )
        self.color_button.setText(f"#{self._color[0]:02X}{self._color[1]:02X}{self._color[2]:02X}")

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(*self._color), self, "选择背景颜色")
        if color.isValid():
            self._color = (color.red(), color.green(), color.blue())
            self._apply_color_style()
            self.changed.emit()

    def _refresh_dest(self) -> None:
        self.dest_button.setText(f"保存到：{self._dest_text()}")

    def _dest_text(self) -> str:
        if self._dest_mode == DEST_CUSTOM and self._custom_dir is not None:
            text = str(self._custom_dir)
            if len(text) > 30:
                text = "…" + text[-29:]
            return text
        return "原图所在文件夹"

    def _show_dest_menu(self) -> None:
        menu = QMenu(self)
        effects.add_popup_shadow(menu)
        act_alongside = menu.addAction("与原图同一文件夹")
        act_custom = menu.addAction("选择文件夹…")
        chosen = menu.exec(
            self.dest_button.mapToGlobal(QPoint(0, self.dest_button.height() + 4))
        )
        if chosen is act_alongside:
            self._dest_mode = DEST_ALONGSIDE
            self._refresh_dest()
            self.changed.emit()
        elif chosen is act_custom:
            self._pick_custom_dir()

    def _pick_custom_dir(self) -> None:
        start = str(self._custom_dir) if self._custom_dir else ""
        path = QFileDialog.getExistingDirectory(self, "选择保存文件夹", start)
        if not path:
            # 取消且此前没有目录：退回默认，避免落在"已选自定义但没路径"的空状态
            if self._custom_dir is None:
                self._dest_mode = DEST_ALONGSIDE
                self._refresh_dest()
                self.changed.emit()
            return
        self._custom_dir = Path(path)
        self._dest_mode = DEST_CUSTOM
        self._refresh_dest()
        self.changed.emit()

    # ------------------------------------------------------------ 取值
    def build_options(self) -> JobOptions:
        """把界面上的两项映射成完整作业参数，其余是固定策略。"""
        kind = (
            BackgroundKind.COLOR if self.bg_color.isChecked() else BackgroundKind.TRANSPARENT
        )
        custom = self._dest_mode == DEST_CUSTOM
        return JobOptions(
            model_key=DEFAULT_MODEL_KEY,
            output_format=OutputFormat.PNG,
            background=BackgroundSpec(kind=kind, color=self._color),
            output_dir=self._custom_dir if custom else None,
            keep_structure=True,
            alongside=not custom,
            workers=0,
            feather=0.0,
            # 界面语义：点一次「开始」就应拿到最新结果，同名输出直接覆盖。
            # 已存在的输出不会被跳过，否则改完背景色再点开始会毫无反应。
            overwrite=True,
            jpeg_quality=92,
        )

    def validate(self) -> str | None:
        if self._dest_mode == DEST_CUSTOM:
            if self._custom_dir is None:
                return "请选择保存文件夹"
            if not self._custom_dir.is_dir():
                return f"保存文件夹不存在：{self._custom_dir}"
        return None

    def set_running(self, running: bool) -> None:
        for widget in (
            self.bg_transparent,
            self.bg_color,
            self.color_button,
            self.dest_button,
        ):
            widget.setEnabled(not running)
        if not running:
            self._sync_enabled()

    def set_has_tasks(self, has_tasks: bool) -> None:  # 兼容旧接口：列表提示由主窗口管理
        return None

    def set_status(self, text: str) -> None:  # 兼容旧接口：状态文字在 ActionBar
        return None

    # ------------------------------------------------------- 供外部使用
    def current_model_key(self) -> str:
        return DEFAULT_MODEL_KEY

    @property
    def dest_mode(self) -> str:
        return self._dest_mode

    @property
    def custom_dir(self) -> Path | None:
        return self._custom_dir

    def set_custom_dir(self, path: Path) -> None:
        """直接设定保存文件夹（供测试脚本与将来的拖放功能使用）。"""
        self._custom_dir = Path(path)
        self._dest_mode = DEST_CUSTOM
        self._refresh_dest()
        self.changed.emit()

    # ------------------------------------------------- 配置持久化
    def state(self) -> dict:
        return {
            "bg": "color" if self.bg_color.isChecked() else "transparent",
            "color": list(self._color),
            "dest": self._dest_mode,
            "dir": str(self._custom_dir) if self._custom_dir else "",
        }

    def restore(self, state: dict) -> None:
        if state.get("bg") == "color":
            self.bg_color.setChecked(True)
        else:
            self.bg_transparent.setChecked(True)

        color = state.get("color")
        if isinstance(color, list) and len(color) == 3:
            self._color = tuple(int(v) for v in color)  # type: ignore[assignment]
            self._apply_color_style()

        raw_dir = str(state.get("dir") or "")
        if raw_dir:
            self._custom_dir = Path(raw_dir)
            if state.get("dest") == DEST_CUSTOM:
                self._dest_mode = DEST_CUSTOM

        self._sync_enabled()
        self._refresh_dest()
