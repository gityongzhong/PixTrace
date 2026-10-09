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
# v0.3.9 收敛过一轮对比度：上一版的边框/高光/强调色都比底色亮太多，几块卡片
# 像"贴"在底上。这里把色阶差整体压小一档——层次还在，但不抢眼。
BG = "#1d1f23"          # 窗体底
BG_PANEL = "#24272d"    # 面板 / 卡片
BG_CARD = "#24272d"
BG_WELL = "#1b1d21"     # 凹槽：列表 / 表头（比窗体底稍深，不再挖得很深）
BG_DROP = "#22252b"     # 空状态拖拽区：比面板只亮一档
BG_DROP_ACTIVE = "#202c3f"
BG_INPUT = "#2a2d33"
BG_FILL = "#2a2d33"     # 次级填充：进度槽、悬停底
BG_HOVER = "#2f333a"
BG_PRESSED = "#353941"
BTN_HOVER = "#2f333a"
BG_SELECTED = "#283d5e"  # 列表选中（降饱和，别在深底上烧起来）
BORDER = "#2e3238"
BORDER_STRONG = "#383c43"
BORDER_HOVER = "#454a53"
HILIGHT = "#343841"     # 卡片顶部 1px 高光：只比边框亮一点
HILIGHT_STRONG = "#41464f"  # 按钮/输入顶部 1px 高光
BG_DISABLED = "#22252a"  # 禁用控件：几乎融进面板
BORDER_DISABLED = "#2b2e34"
BG_GLYPH_TOP = "#272b35"  # 空状态图标小卡
BG_GLYPH_BOTTOM = "#212530"
BORDER_GLYPH = "#333846"
HILIGHT_GLYPH = "#3f4553"
TEXT = "#cfd1d6"
TEXT_DIM = "#949aa5"
TEXT_FAINT = "#6b7280"
TEXT_ON_ACCENT = "#ffffff"
ACCENT = "#4171cd"      # 比上一版的 #3d7df0 降了一档饱和与亮度
ACCENT_HOVER = "#5785da"
ACCENT_PRESSED = "#355fb3"
ACCENT_SOFT = "#283d5e"
ACCENT_HILIGHT = "#729adf"
OK = "#4ec9b0"
WARN = "#d9b36c"
ERR = "#f28b82"
OK_TEXT = "#5ecfb8"
WARN_TEXT = "#e0c088"
ERR_TEXT = "#f28b82"
PREVIEW_BG = "#151619"
CHECKER_LIGHT = "#3a3d44"   # 预览窗透明区棋盘格
CHECKER_DARK = "#2c2f35"

# 主窗口中央区：极淡的纵向渐变（比上一版跨度更小，几乎察觉不到但不再是死平的底色）
SURFACE_TOP = "#212429"
SURFACE_BOTTOM = "#1a1c20"

FOCUS_RING = "rgba(65, 113, 205, 0.45)"
TRACK = "rgba(255, 255, 255, 0.06)"
ROW_HOVER = "rgba(255, 255, 255, 0.04)"

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
/* ---------- 拖拽条 / 空状态拖拽区 ----------
   这两块的底色与边框**不在这里**：它们由 paintEvent 自绘（app/ui/anim.py 的
   paint_tint_frame）。原因很实在——QSS 的状态切换是瞬时硬切，插不出过渡的
   中间色，拖拽悬停时会「啪」地跳一下。
   这里刻意不再声明 background / border：声明了也只会叠在自绘结果上。
   自绘用的色号：BG_PANEL / BG_DROP（常态）→ BG_DROP_ACTIVE（悬停），
   边框 BORDER_STRONG → ACCENT，顶部高光 HILIGHT_STRONG → ACCENT。 */

/* 空状态图标底：一块带渐变的圆角小卡，图标不再裸放在空底上 */
QFrame[role="glyphbox"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {BG_GLYPH_TOP}, stop:1 {BG_GLYPH_BOTTOM});
    border: 1px solid {BORDER_GLYPH};
    border-top-color: {HILIGHT_GLYPH};
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
    background-color: {BG_DISABLED};
    border-color: {BORDER_DISABLED};
    border-top-color: {BORDER_DISABLED};
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
    background-color: {BG_DISABLED};
    border-color: {BORDER_DISABLED};
    border-top-color: {HILIGHT};
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
    border-bottom: 1px solid {BORDER};
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
