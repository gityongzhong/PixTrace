"""界面主题（VS Code 式暗色）。

色板与形态对齐 v0.2.0 的原始观感：
- #1e1e1e 窗体底 + #252526 面板，1px 实线边框（#3c3c3c），5px 小圆角
- 唯一强调色 #3b82f6，状态色随 VS Code 语义：完成 #4ec9b0、失败 #f48771
- 列表带表头与交替行色，控件是表单语言（radio、方按钮），不走苹果风

把 QSS 写成 Python 常量而不是 .qss 文件，是为了打包时不必处理资源路径
（PyInstaller 对数据文件的路径处理是个常见的坑）。
"""

from __future__ import annotations

# ---------------------------------------------------------------- 字体
UI_FONT = (
    '"Segoe UI", "Microsoft YaHei UI", "PingFang SC", "Helvetica Neue", sans-serif'
)
MONO_FONT = '"Cascadia Mono", "Consolas", monospace'

# ---------------------------------------------------------------- 色板
BG = "#1e1e1e"          # 窗体底
BG_PANEL = "#252526"    # 面板 / 卡片
BG_CARD = "#252526"
BG_INPUT = "#2d2d30"
BG_FILL = "#2d2d30"     # 次级填充：进度槽、悬停底
BG_HOVER = "#333333"
BG_PRESSED = "#3c3c3c"
BTN_HOVER = "#333333"
BG_SELECTED = "#094771"  # 列表选中（VS Code list.activeSelectionBackground）
BORDER = "#3c3c3c"
BORDER_STRONG = "#4b4b4b"
BORDER_HOVER = "#5a5a5a"
TEXT = "#cccccc"
TEXT_DIM = "#9a9a9a"
TEXT_FAINT = "#6e6e6e"
TEXT_ON_ACCENT = "#ffffff"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#60a5fa"
ACCENT_PRESSED = "#2563eb"
OK = "#4ec9b0"
WARN = "#cca700"
ERR = "#f48771"
OK_TEXT = "#4ec9b0"
WARN_TEXT = "#e0c088"
ERR_TEXT = "#f48771"
PREVIEW_BG = "#1e1e1e"
CHECKER_LIGHT = "#3a3a3c"   # 预览窗透明区棋盘格
CHECKER_DARK = "#2c2c2e"

STATUS_COLORS = {
    "等待": TEXT_FAINT,
    "处理中": ACCENT,
    "完成": OK_TEXT,
    "跳过": WARN_TEXT,
    "失败": ERR_TEXT,
}


def rgb(hex_color: str) -> tuple[int, int, int]:
    """'#RRGGBB' -> (r, g, b)。供需要算混合的内联样式用。"""
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _render() -> str:
    return f"""
QWidget {{
    background-color: transparent;
    color: {TEXT};
    font-family: {UI_FONT};
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {BG};
}}

/* ---------- 文字层级 ---------- */
QLabel {{
    background-color: transparent;
}}
QLabel[role="hint"] {{
    font-size: 12px;
    color: {TEXT_DIM};
}}
QLabel[role="faint"] {{
    font-size: 11px;
    color: {TEXT_FAINT};
}}

/* ---------- 容器 ---------- */
QFrame[role="panel"] {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 5px;
}}
QFrame[role="separator"] {{
    background-color: {BORDER};
    border: none;
}}
QFrame[role="dropbar"] {{
    background-color: {BG_PANEL};
    border: 1px dashed {BORDER_STRONG};
    border-radius: 5px;
}}
QFrame[role="dropbar"][active="true"] {{
    border: 1px solid {ACCENT};
    background-color: #22303f;
}}

/* 空状态整块拖拽区：比提示条更抢眼，但仍是虚线框不与列表边框混淆 */
QFrame[role="droparea"] {{
    background-color: {BG_PANEL};
    border: 1px dashed {BORDER_STRONG};
    border-radius: 6px;
}}
QFrame[role="droparea"][active="true"] {{
    border: 1px solid {ACCENT};
    background-color: #22303f;
}}
QLabel[role="droptitle"] {{
    font-size: 15px;
    color: {TEXT};
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background-color: {BG_INPUT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 14px;
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: {BTN_HOVER};
    border-color: {BORDER_HOVER};
}}
QPushButton:pressed {{
    background-color: {BG_PRESSED};
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
    background-color: {BG_FILL};
    border-color: {BORDER};
}}

/* 工具条右侧带下拉菜单的按钮：给箭头留出位置 */
QPushButton[role="menubtn"] {{
    padding-right: 24px;
}}
QPushButton[role="menubtn"]::menu-indicator {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    right: 8px;
}}

/* 底部链接条里的文字型按钮（赞赏） */
QPushButton[role="flat"] {{
    border: none;
    background: transparent;
    color: {ACCENT};
    padding: 2px 4px;
}}
QPushButton[role="flat"]:hover {{
    color: {ACCENT_HOVER};
    text-decoration: underline;
}}
QPushButton[role="flat"]:disabled {{
    color: {TEXT_FAINT};
    background: transparent;
}}

QPushButton[role="primary"] {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: {TEXT_ON_ACCENT};
    font-weight: 500;
    padding: 5px 20px;
}}
QPushButton[role="primary"]:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton[role="primary"]:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {ACCENT_PRESSED};
}}
QPushButton[role="primary"]:disabled {{
    background-color: {BG_FILL};
    border-color: {BORDER};
    color: {TEXT_FAINT};
}}

/* 色块按钮（背景颜色） */
QPushButton[role="swatch"] {{
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
    padding: 2px 10px;
    font-size: 12px;
    min-height: 18px;
}}

/* ---------- 输入控件 ---------- */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QPlainTextEdit {{
    background-color: {BG_INPUT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 20px;
    selection-background-color: {ACCENT};
    selection-color: {TEXT_ON_ACCENT};
}}
QComboBox:hover, QLineEdit:hover {{
    border-color: {BORDER_HOVER};
}}
QComboBox:focus, QLineEdit:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    color: {TEXT};
    selection-background-color: {BG_SELECTED};
    outline: none;
}}

QRadioButton {{
    spacing: 6px;
    background-color: transparent;
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    background-color: {BG_INPUT};
}}
QRadioButton::indicator:hover {{
    border-color: {BORDER_HOVER};
}}
QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border: 3px solid {BG_PANEL};
}}
QRadioButton:disabled {{
    color: {TEXT_FAINT};
}}

/* ---------- 列表 ---------- */
QTreeWidget, QListWidget {{
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    outline: none;
    alternate-background-color: #232323;
    show-decoration-selected: 1;
}}
QTreeWidget[dragover="true"], QListWidget[dragover="true"] {{
    border: 1px solid {ACCENT};
}}
QTreeWidget::item, QListWidget::item {{
    height: 26px;
    padding: 0 4px;
    border: none;
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: {BG_SELECTED};
    color: {TEXT};
}}
QTreeWidget::item:hover, QListWidget::item:hover {{
    background-color: {BG_FILL};
}}
QHeaderView::section {{
    background-color: {BG};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 5px 8px;
    font-size: 12px;
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* ---------- 进度条 ---------- */
QProgressBar {{
    background-color: {BG_FILL};
    border: none;
    border-radius: 3px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

/* ---------- 滚动条：细、无箭头、悬停加深 ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDER_HOVER};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {BORDER_HOVER};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* ---------- 弹出菜单与提示（没有菜单栏，只有工具条上的菜单按钮） ---------- */
QMenu {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 28px 5px 14px;
    color: {TEXT};
}}
QMenu::item:selected {{
    background-color: {BG_SELECTED};
}}
QMenu::item:disabled {{
    color: {TEXT_FAINT};
}}
QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 4px 6px;
}}
QToolTip {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
}}

QMessageBox {{
    background-color: {BG_PANEL};
}}
QMessageBox QLabel {{
    color: {TEXT};
}}
QStatusBar {{
    background-color: {BG};
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
}}
"""


STYLE = _render()


def apply(app, theme: str | None = None) -> None:
    """统一入口：Fusion 基样式 + 暗色 QSS。

    theme 参数仅为兼容旧调用方签名（scripts/shot_gui.py 曾传 "light"/"dark"），
    现在只有一套暗色主题，传入值被忽略。
    """
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
