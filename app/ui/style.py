"""界面主题（冷调暗色）。

设计要点（相对 v0.2 的 VS Code 灰）：
- 色板从「中性灰」换成微冷灰（色相 ~222）：底 #1a1c20 / 面板 #262930 / 输入 #2b2e35。
  面板与底色亮度差从 3% 拉到 8%，卡片才浮得起来——这是「有质感」的第一来源。
- 每个可交互表面顶部压一条 1px 高光（border-top-color 提亮），模拟实体边缘受光；
  这是 QSS 唯一的「高光」手段（QSS 不支持 box-shadow / inset 阴影）。
- 统一形态：卡片圆角 8、按钮与输入 6、进度条与滚动条全圆角；按钮长到 30px 高。
- 列表行高 30px，去掉那个几乎看不见的交替行（只剩脏），改用悬停高亮 + 左侧强调条。
- 强调色 #3d7df0，主按钮带渐变与上下边缘高光。

仍然把 QSS 写成 Python 常量而不是 .qss 文件：打包时不必处理资源路径
（PyInstaller 对数据文件的路径处理是个常见的坑）。

投影不在这里：QSS 画不出 box-shadow，由 app/ui/effects.py 用
QGraphicsDropShadowEffect 补，见该模块。
"""

from __future__ import annotations

# ---------------------------------------------------------------- 字体
UI_FONT = (
    '"Segoe UI", "Microsoft YaHei UI", "PingFang SC", "Helvetica Neue", sans-serif'
)
MONO_FONT = '"Cascadia Mono", "Consolas", monospace'

# ---------------------------------------------------------------- 色板
BG = "#1a1c20"          # 窗体底
BG_PANEL = "#262930"    # 面板 / 卡片
BG_CARD = "#262930"
BG_WELL = "#17181c"     # 凹槽：列表 / 表头（比窗体底更深）
BG_INPUT = "#2b2e35"
BG_FILL = "#2b2e35"     # 次级填充：进度槽、悬停底
BG_HOVER = "#31353d"
BG_PRESSED = "#383d46"
BTN_HOVER = "#31353d"
BG_SELECTED = "#2b4a7d"  # 列表选中
BORDER = "#33363d"
BORDER_STRONG = "#3d414a"
BORDER_HOVER = "#4a4f59"
HILIGHT = "#3a3f49"     # 卡片顶部 1px 高光
HILIGHT_STRONG = "#4a505c"  # 按钮/输入顶部 1px 高光
TEXT = "#d6d7db"
TEXT_DIM = "#9aa0ab"
TEXT_FAINT = "#6b7280"
TEXT_ON_ACCENT = "#ffffff"
ACCENT = "#3d7df0"
ACCENT_HOVER = "#5b93f5"
ACCENT_PRESSED = "#2f68d8"
ACCENT_SOFT = "#2b4a7d"
ACCENT_HILIGHT = "#86b4ff"
OK = "#4ec9b0"
WARN = "#d9b36c"
ERR = "#f28b82"
OK_TEXT = "#5ecfb8"
WARN_TEXT = "#e0c088"
ERR_TEXT = "#f28b82"
PREVIEW_BG = "#151619"
CHECKER_LIGHT = "#3a3d44"   # 预览窗透明区棋盘格
CHECKER_DARK = "#2c2f35"

# 主窗口中央区：极淡的纵向渐变，避免整块死平的底色
SURFACE_TOP = "#1f2229"
SURFACE_BOTTOM = "#17181c"

FOCUS_RING = "rgba(61, 125, 240, 0.45)"
TRACK = "rgba(255, 255, 255, 0.07)"
ROW_HOVER = "rgba(255, 255, 255, 0.05)"

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


def mono_font(pixel_size: int = 12):
    """等宽字体：耗时这类数字用它对齐才整齐（QSS 没法按列设字体）。"""
    from PySide6.QtGui import QFont

    font = QFont()
    font.setFamilies(["Cascadia Mono", "Consolas", "monospace"])
    font.setPixelSize(pixel_size)
    return font


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

/* 中央区渐变底：挂在 objectName="surface" 上（需 WA_StyledBackground） */
QWidget#surface {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {SURFACE_TOP}, stop:0.5 {BG}, stop:1 {SURFACE_BOTTOM});
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
QLabel[role="droptitle"] {{
    font-size: 16px;
    font-weight: 500;
    color: {TEXT};
}}

/* ---------- 容器：底色 + 1px 边框 + 顶部高光 ---------- */
QFrame[role="panel"] {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-top-color: {HILIGHT};
    border-radius: 8px;
}}
QFrame[role="separator"] {{
    background-color: {BORDER};
    border: none;
}}
QFrame[role="dropbar"] {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_STRONG};
    border-top-color: {HILIGHT_STRONG};
    border-radius: 8px;
}}
QFrame[role="dropbar"][active="true"] {{
    border: 1px solid {ACCENT};
    background-color: #223047;
}}

/* 空状态整块拖拽区：实线 + 比面板亮一档的底，虚线是「低保真」观感的主要来源 */
QFrame[role="droparea"] {{
    background-color: #23262d;
    border: 1px solid {BORDER_STRONG};
    border-top-color: {HILIGHT_STRONG};
    border-radius: 10px;
}}
QFrame[role="droparea"][active="true"] {{
    border: 1px solid {ACCENT};
    background-color: #223047;
}}

/* 空状态图标底：一块带渐变的圆角小卡，图标不再裸放在空底上 */
QFrame[role="glyphbox"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #2c3342, stop:1 #232833);
    border: 1px solid #3d4453;
    border-top-color: #4d5668;
    border-radius: 18px;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background-color: {BG_INPUT};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-top-color: {HILIGHT_STRONG};
    border-radius: 6px;
    padding: 6px 16px;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: {BTN_HOVER};
    border-color: {BORDER_HOVER};
}}
QPushButton:pressed {{
    background-color: {BG_PRESSED};
    border-color: {BORDER_HOVER};
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
    background-color: #23262c;
    border-color: #2c2f36;
    border-top-color: #2c2f36;
}}
/* 不给 QPushButton 全局 focus 描边：开局焦点落在「添加图片」上会常亮一整块蓝，
   像被误选中；focus 反馈交给输入类控件 */

/* 工具条右侧带下拉菜单的按钮：给箭头留出位置 */
QPushButton[role="menubtn"] {{
    padding-right: 26px;
}}
QPushButton[role="menubtn"]::menu-indicator {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    right: 9px;
}}

/* 底部链接条里的文字型按钮（赞赏） */
QPushButton[role="flat"] {{
    border: none;
    background: transparent;
    color: {ACCENT};
    padding: 2px 4px;
    border-radius: 4px;
}}
QPushButton[role="flat"]:hover {{
    color: {ACCENT_HOVER};
    text-decoration: underline;
}}
QPushButton[role="flat"]:disabled {{
    color: {TEXT_FAINT};
    background: transparent;
}}

/* 主按钮：上下边缘各一条高光/暗边，做出实体感 */
QPushButton[role="primary"] {{
    background-color: {ACCENT};
    color: {TEXT_ON_ACCENT};
    border: 1px solid {ACCENT_HOVER};
    border-top-color: {ACCENT_HILIGHT};
    border-bottom-color: {ACCENT_PRESSED};
    font-weight: 500;
    padding: 6px 22px;
}}
QPushButton[role="primary"]:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HILIGHT};
    border-bottom-color: {ACCENT};
}}
QPushButton[role="primary"]:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {ACCENT_PRESSED};
}}
QPushButton[role="primary"]:disabled {{
    background-color: #2a2d34;
    border-color: #343841;
    border-top-color: #3b3f49;
    color: {TEXT_FAINT};
}}

/* 色块按钮（背景颜色） */
QPushButton[role="swatch"] {{
    border: 1px solid {BORDER_STRONG};
    border-top-color: {HILIGHT_STRONG};
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 12px;
    min-height: 18px;
}}

/* ---------- 输入控件 ---------- */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QPlainTextEdit {{
    background-color: {BG_INPUT};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
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
    background-color: {BG_INPUT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    color: {TEXT};
    selection-background-color: {ACCENT_SOFT};
    outline: none;
}}

QRadioButton {{
    spacing: 7px;
    background-color: transparent;
}}
QRadioButton::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    background-color: {BG_INPUT};
}}
QRadioButton::indicator:hover {{
    border-color: {BORDER_HOVER};
}}
QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border: 4px solid {BG_PANEL};
}}
QRadioButton:disabled {{
    color: {TEXT_FAINT};
}}

/* ---------- 列表：深色凹槽 + 悬停高亮 + 左侧强调条 ---------- */
QTreeWidget, QListWidget {{
    background-color: {BG_WELL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    outline: none;
    show-decoration-selected: 1;
}}
QTreeWidget[dragover="true"], QListWidget[dragover="true"] {{
    border: 1px solid {ACCENT};
}}
QTreeWidget::item, QListWidget::item {{
    height: 30px;
    padding: 0 8px;
    border: none;
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: {ACCENT_SOFT};
    color: {TEXT};
}}
/* 注意：这里不能加 border-left 强调条——::item 按列生效，会让选中行的
   每一列之间都竖起一条蓝线。真要强调条得写 delegate，收益不值。 */
QTreeWidget::item:hover, QListWidget::item:hover {{
    background-color: {ROW_HOVER};
}}
QHeaderView::section {{
    background-color: {BG_WELL};
    color: {TEXT_FAINT};
    border: none;
    border-bottom: 1px solid #2c2f36;
    padding: 7px 10px;
    font-size: 12px;
}}

/* ---------- 进度条 ---------- */
QProgressBar {{
    background-color: {TRACK};
    border: none;
    border-radius: 4px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {ACCENT_HOVER}, stop:1 {ACCENT});
    border-radius: 4px;
}}

/* ---------- 滚动条：细、无箭头、悬停加深 ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDER_HOVER};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 5px;
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

/* ---------- 弹出菜单与提示 ---------- */
QMenu {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 28px 7px 14px;
    border-radius: 5px;
    color: {TEXT};
}}
QMenu::item:selected {{
    background-color: {ACCENT_SOFT};
}}
QMenu::item:disabled {{
    color: {TEXT_FAINT};
}}
QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 5px 8px;
}}
QToolTip {{
    background-color: {BG_INPUT};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 6px 10px;
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
