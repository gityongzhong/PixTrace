"""界面主题（流晷暗色）。

v0.5.0 对齐用户上一款产品「流晷计时器」的设计语言，核心结论来自那次对比：
对比度高不等于突兀——流晷的对比度比上一版 PixTrace 高得多，但很干净。区别在：

- **底色够深**（#0f1013 近黑）：面板（#17181c）靠明度差自然浮起，
  不需要「1px 边框 + 顶部高光 + 投影」三件套来证明层次。
  之前几版的「突兀感」正是这些细碎装饰叠出来的；本版把边框和高光基本拿掉。
- **强调色纯而收敛**（#1f7fff 亮蓝）：只出现在焦点处——选中行、主按钮、
  单选点、链接。面积小而纯，所以亮也不吵。上一版把蓝压灰（#4171cd）
  治标不治本，界面反而发闷。
- **选中 = 实心亮蓝块 + 白字**（流晷式），不再用暗蓝底灰字。
- 形态放宽：圆角 8/10，按钮 min-height 22。

仍然把 QSS 写成 Python 常量而不是 .qss 文件：打包时不必处理资源路径
（PyInstaller 对数据文件的路径处理是个常见的坑）。

投影不在这里：QSS 画不出 box-shadow，由 app/ui/effects.py 用
QGraphicsDropShadowEffect 补。动画/自绘过渡见 app/ui/anim.py。
"""

from __future__ import annotations

# ---------------------------------------------------------------- 字体
UI_FONT = (
    '"Segoe UI", "Microsoft YaHei UI", "PingFang SC", "Helvetica Neue", sans-serif'
)
MONO_FONT = '"Cascadia Mono", "Consolas", monospace'

# ---------------------------------------------------------------- 色板
# 常量名是既有接口（anim.py 自绘、main_window、preview、model_dialog 都引用），
# 只换值不改名。
BG = "#0f1013"          # 窗体底：近黑（流晷同款深度）
BG_PANEL = "#17181c"    # 面板 / 卡片：靠明度差浮起，无边框
BG_CARD = "#17181c"
BG_WELL = "#121317"     # 凹槽：列表 / 表头
BG_DROP = "#15161b"     # 空状态拖拽区：比面板亮一丝
BG_DROP_ACTIVE = "#14294f"  # 拖拽悬停：带蓝的深底
BG_INPUT = "#1e2025"
BG_FILL = "#1e2025"     # 次级填充：进度槽、悬停底
BG_HOVER = "#25272e"
BG_PRESSED = "#191b1f"  # 按压变暗（比变亮更符合「按下去」的直觉）
BTN_HOVER = "#25272e"
BG_SELECTED = "#1f7fff"  # 列表选中：实心亮蓝块（流晷式）
BORDER = "#1d1f24"      # 极淡：深底下只留一条「若隐若现」的线
BORDER_STRONG = "#26282e"
BORDER_HOVER = "#34373f"
HILIGHT = "#1d1f24"     # 顶部高光已弱化到与边框同色：不再作为分层手段
HILIGHT_STRONG = "#2b2e35"
BG_DISABLED = "#15161a"
BORDER_DISABLED = "#202227"
BG_GLYPH_TOP = "#1b1e26"   # 空状态图标小卡
BG_GLYPH_BOTTOM = "#13151b"
BORDER_GLYPH = "#242835"
HILIGHT_GLYPH = "#2c3242"
TEXT = "#e8eaee"
TEXT_DIM = "#9aa0ab"
TEXT_FAINT = "#656b74"
TEXT_ON_ACCENT = "#ffffff"
ACCENT = "#1f7fff"      # 流晷同款亮蓝，只用在焦点处
ACCENT_HOVER = "#3d90ff"
ACCENT_PRESSED = "#1668d6"
ACCENT_SOFT = "#142a52"  # 下拉列表等次级选中底
ACCENT_HILIGHT = "#69a7ff"
OK = "#3fd0a4"
WARN = "#d9b36c"
ERR = "#f28b82"
OK_TEXT = "#43d9a8"
WARN_TEXT = "#e3c084"
ERR_TEXT = "#ff8078"
PREVIEW_BG = "#0b0c0e"
CHECKER_LIGHT = "#292c33"   # 预览窗透明区棋盘格
CHECKER_DARK = "#1e2025"

# 主窗口中央区：极淡的纵向渐变（底已近黑，跨度刻意很小）
SURFACE_TOP = "#131419"
SURFACE_BOTTOM = "#0c0d10"

FOCUS_RING = "rgba(31, 127, 255, 0.5)"
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
