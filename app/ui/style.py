"""界面主题（苹果深色 · macOS Sonoma 取色）。

v0.6.0 换成苹果深色：底色从「近黑」抬到中性深灰（#1c1c1e），面板比底色亮一档
（#252527）浮起，强调色改系统蓝 #0A84FF，按钮改灰色填充胶囊、分隔线压到发丝级。

这个决定和 v0.3.1 那次「苹果风被否」不冲突——那次踩的是浅色 + 大圆角 + 毛玻璃
三件套，跟工具软件的调性打架；这次只借苹果深色的**取色与层次逻辑**，布局、
动效、交互全部沿用流晷那套已经验证过的骨架，所以只是换皮，不是重做。

仍然把 QSS 写成 Python 常量而不是 .qss 文件：打包时不必处理资源路径
（PyInstaller 对数据文件的路径处理是个常见的坑）。

投影不在这里：QSS 画不出 box-shadow，由 app/ui/effects.py 用
QGraphicsDropShadowEffect 补。动画/自绘过渡见 app/ui/anim.py。
"""

from __future__ import annotations

# ---------------------------------------------------------------- 字体
# 苹果的 SF Pro 拿不到授权，Windows 上只能退到系统中文字体；字重靠 QSS 的
# font-weight 微调，不要试图去模拟 SF 的字形。
UI_FONT = (
    '"Segoe UI", "Microsoft YaHei UI", "PingFang SC", "Helvetica Neue", sans-serif'
)
MONO_FONT = '"Cascadia Mono", "Consolas", monospace'

# ---------------------------------------------------------------- 色板
# 常量名是既有接口（anim.py 自绘、main_window、preview、model_dialog 都引用），
# 只换值不改名。
BG = "#1c1c1e"          # 窗体底：中性深灰（苹果深色的 windowBackground）
BG_PANEL = "#252527"    # 面板 / 卡片：比底色亮一档，靠明度差浮起
BG_CARD = "#252527"
BG_WELL = "#1c1c1e"     # 凹槽：列表 / 表头与窗体同色（苹果列表不另铺底）
BG_DROP = "#242426"     # 空状态拖拽区：比窗体亮一点，像一块可投放的板
BG_DROP_ACTIVE = "#102c4a"  # 拖拽悬停：系统蓝的深色底
BG_INPUT = "#3a3a3c"    # 控件填充：苹果的灰色胶囊按钮
BG_FILL = "#3a3a3c"     # 次级填充：进度槽、悬停底
BG_HOVER = "#3a3a3c"
BG_PRESSED = "#2c2c2e"  # 按压变暗（比变亮更符合「按下去」的直觉）
BTN_HOVER = "#48484a"
BG_SELECTED = "#0a84ff"  # 列表选中：系统蓝实心块
BORDER = "#38383a"      # 发丝线：只用来分栏，不用来「撑」层次
BORDER_STRONG = "#3a3a3c"
BORDER_HOVER = "#545456"
HILIGHT = "#38383a"     # 顶部高光与边框同色：不作为分层手段
HILIGHT_STRONG = "#48484a"
BG_DISABLED = "#2c2c2e"
BORDER_DISABLED = "#333335"
BG_GLYPH_TOP = "#2c2c2e"   # 空状态图标小卡
BG_GLYPH_BOTTOM = "#242426"
BORDER_GLYPH = "#3a3a3c"
HILIGHT_GLYPH = "#48484a"
TEXT = "#f5f5f7"        # 苹果的 label
TEXT_DIM = "#a1a1a6"    # secondaryLabel
TEXT_FAINT = "#6e6e73"  # tertiaryLabel
TEXT_ON_ACCENT = "#ffffff"
ACCENT = "#0a84ff"      # 系统蓝（深色模式），只用在焦点处
ACCENT_HOVER = "#409cff"
ACCENT_PRESSED = "#0060df"
ACCENT_SOFT = "rgba(10, 132, 255, 0.20)"  # 下拉列表等次级选中底
ACCENT_HILIGHT = "#64b5ff"
OK = "#30d158"
WARN = "#ffd60a"
ERR = "#ff453a"
OK_TEXT = "#30d158"
WARN_TEXT = "#ffd60a"
ERR_TEXT = "#ff453a"
PREVIEW_BG = "#1c1c1e"
CHECKER_LIGHT = "#2c2c2e"   # 预览窗透明区棋盘格
CHECKER_DARK = "#242426"

# 主窗口中央区：苹果深色是平的，不再做纵向渐变
SURFACE_TOP = "#1c1c1e"
SURFACE_BOTTOM = "#1c1c1e"

FOCUS_RING = "rgba(10, 132, 255, 0.5)"
TRACK = "rgba(255, 255, 255, 0.12)"
ROW_HOVER = "rgba(255, 255, 255, 0.06)"

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

/* ---------- 容器：无边框，靠明度差浮起（流晷式） ---------- */
QFrame[role="panel"] {{
    background-color: {BG_PANEL};
    border: none;
    border-radius: 10px;
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

/* ---------- 按钮：无边框纯明度差 ---------- */
QPushButton {{
    background-color: {BG_INPUT};
    color: {TEXT};
    border: none;
    border-radius: 8px;
    padding: 6px 18px;
    min-height: 22px;
}}
QPushButton:hover {{
    background-color: {BTN_HOVER};
}}
QPushButton:pressed {{
    background-color: {BG_PRESSED};
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
    background-color: {BG_DISABLED};
}}
/* 不给 QPushButton 全局 focus 描边：开局焦点落在「添加图片」上会常亮一整块蓝，
   像被误选中；focus 反馈交给输入类控件 */

/* 带下拉菜单的按钮：给箭头留出位置。
   目前没有控件在用（v0.4.1 移除了工具条右侧的「设置」菜单），样式先留着，
   以后要在别处挂菜单按钮直接加 role="menubtn" 即可。 */
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

/* 主按钮：纯亮蓝块，无边框无高光（流晷的「开始」按钮同款） */
QPushButton[role="primary"] {{
    background-color: {ACCENT};
    color: {TEXT_ON_ACCENT};
    border: none;
    font-weight: 500;
    padding: 6px 24px;
}}
QPushButton[role="primary"]:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton[role="primary"]:pressed {{
    background-color: {ACCENT_PRESSED};
}}
QPushButton[role="primary"]:disabled {{
    background-color: {BG_DISABLED};
    color: {TEXT_FAINT};
}}

/* 色块按钮（背景颜色）：色块需要一圈淡边，浅色色块才看得清边界 */
QPushButton[role="swatch"] {{
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 3px 10px;
    font-size: 12px;
    min-height: 18px;
}}

/* ---------- 输入控件：平时无边框，focus 才亮蓝描边 ---------- */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QPlainTextEdit {{
    background-color: {BG_INPUT};
    color: {TEXT};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px 10px;
    min-height: 22px;
    selection-background-color: {ACCENT};
    selection-color: {TEXT_ON_ACCENT};
}}
QComboBox:hover, QLineEdit:hover {{
    background-color: {BG_HOVER};
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
    border-radius: 8px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {TEXT_ON_ACCENT};
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

/* ---------- 列表：深色凹槽 + 悬停高亮 + 实心亮蓝选中块 ---------- */
QTreeWidget, QListWidget {{
    background-color: {BG_WELL};
    border: none;
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
    background-color: {BG_SELECTED};
    color: {TEXT_ON_ACCENT};
}}
/* 注意：这里不能加 border-left 强调条——::item 按列生效，会让选中行的
   每一列之间都竖起一条蓝线。真要强调条得写 delegate，收益不值。
   选中行的状态列文字仍由代码里 setForeground 按状态着色，在亮蓝底上均可读。 */
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
    border: none;
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 28px 7px 14px;
    border-radius: 6px;
    color: {TEXT};
}}
QMenu::item:selected {{
    background-color: {ACCENT};
    color: {TEXT_ON_ACCENT};
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
    border-radius: 8px;
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
