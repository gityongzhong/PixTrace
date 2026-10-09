"""主窗口。

界面刻意做到最小：拖入图片 → 选背景（透明 / 纯色）→ 开始处理。
模型档位、输出格式、并发、羽化这些工程参数都不出现在界面上（见 settings_panel），
所以这里也没有筛选器、没有重跑按钮：失败的项在列表里标红，直接再点一次「开始处理」
就会重新处理（规划阶段会跳过已成功生成的输出）。

布局自上而下：工具条 → [大拖拽区 ⇄ 任务列表] → 设置面板 → 动作行（状态/进度/取消/开始处理）
→ 底部链接条。没有菜单栏：文件类操作在工具条左侧，模型管理 / 关于等在工具条右侧「设置」菜单里。
列表为空时 44px 提示条隐藏，整块内容区由 DropArea 接管。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QKeySequence, QShortcut, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..batch.planner import build_tasks
from ..core.models import DEFAULT_MODEL_KEY, resolve_model
from ..core.types import JobOptions, Task, TaskStatus
from ..infra import model_store, paths
from . import effects, style
from .controller import BatchController, status_of
from .dropzone import DEFAULT_HINT as DEFAULT_DROP_HINT
from .dropzone import DEFAULT_TITLE as DEFAULT_DROP_TITLE
from .dropzone import DropArea
from .model_dialog import ModelManagerDialog
from .preview import PreviewWindow
from .settings_panel import SettingsPanel

COLUMNS = ("文件", "状态", "耗时")
SRC_ROLE = Qt.UserRole
REPLAN_DELAY_MS = 200
TITLE = "PixTrace · 去背景"
ROW_HEIGHT = 30
DEFAULT_SIZE = (860, 560)  # 开窗尺寸
MIN_SIZE = (860, 560)  # 下限，再小设置行会挤到换行
GEOMETRY_KEY = "window/geometry2"  # 尾号跟默认尺寸策略走，改尺寸就 +1
LEGACY_GEOMETRY_KEY = "window/geometry"
GITHUB_URL = "https://github.com/gityongzhong/PixTrace"  # 占位，仓库建好后替换


def _status_brush(status: TaskStatus) -> QBrush:
    return QBrush(QColor(_STATUS_HEX.get(status, style.TEXT_FAINT)))


_STATUS_HEX = {
    TaskStatus.PENDING: style.TEXT_FAINT,
    TaskStatus.DONE: style.OK_TEXT,
    TaskStatus.SKIPPED: style.WARN_TEXT,
    TaskStatus.FAILED: style.ERR_TEXT,
}


class DropBar(QFrame):
    """44px 的拖拽提示条。拖拽事件在主窗口处理，这里只负责显示。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "dropbar")
        self.setFixedHeight(44)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("把图片或文件夹拖到这里")
        self.label.setAlignment(Qt.AlignCenter)
        row.addWidget(self.label)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_message(self, text: str) -> None:
        self.label.setText(text)


class FooterBar(QFrame):
    """窗口最底部的链接条：GitHub 项目主页 + 赞赏入口，居中。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "panel")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 7, 12, 7)
        row.setSpacing(14)

        row.addStretch(1)
        self.github_label = QLabel(
            f'<a href="{GITHUB_URL}" '
            f'style="color: {style.ACCENT}; text-decoration: none;">GitHub 项目主页</a>'
        )
        self.github_label.setOpenExternalLinks(True)
        self.github_label.setToolTip(GITHUB_URL)
        row.addWidget(self.github_label)

        line = QFrame()
        line.setProperty("role", "separator")
        line.setFixedSize(1, 14)
        row.addWidget(line)

        self.support_button = QPushButton("赞赏")
        self.support_button.setProperty("role", "flat")
        self.support_button.setToolTip("请作者喝杯咖啡")
        row.addWidget(self.support_button)
        row.addStretch(1)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(TITLE)
        # 默认按最小尺寸开窗：小屏笔记本上不占满桌面，用户想大自己拉
        self.resize(*DEFAULT_SIZE)
        self.setMinimumSize(*MIN_SIZE)
        self.setAcceptDrops(True)

        icon_path = paths.resource_dir() / "assets" / "pixtrace.png"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._inputs: list[Path] = []
        self._tasks: list[Task] = []
        self._task_map: dict[str, Task] = {}
        self._rows: dict[str, QTreeWidgetItem] = {}
        self._started_at = 0.0
        self._store = QSettings("pixtrace", "pixtrace")

        self.controller = BatchController(self)

        # 参数变化即重扫目录；目录很大时扫描有开销，做个防抖
        self._replan_timer = QTimer(self)
        self._replan_timer.setSingleShot(True)
        self._replan_timer.setInterval(REPLAN_DELAY_MS)
        self._replan_timer.timeout.connect(self._replan)

        self._build_ui()
        self._connect()
        self._restore_state()
        self._sync_center()
        self._update_hint()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        # 渐变底挂在中央区（QSS 的 qlineargradient），纯 QWidget 需要显式开启
        # WA_StyledBackground 才会去画样式表里的背景
        central.setObjectName("surface")
        central.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(central)
        wrap = QVBoxLayout(central)
        wrap.setContentsMargins(10, 0, 10, 10)
        wrap.setSpacing(9)

        wrap.addWidget(self._build_toolbar())

        self.dropbar = DropBar()
        wrap.addWidget(self.dropbar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(list(COLUMNS))
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        # 交替行底色与列表底只差几个灰阶，看着只是脏，改用悬停高亮区分
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 76)

        # 列表为空时整块内容区就是拖拽区，有输入后换成任务列表
        self.drop_area = DropArea()
        effects.add_card_shadow(self.drop_area, radius=14, dy=4)
        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(self.drop_area)
        self.center_stack.addWidget(self.tree)
        wrap.addWidget(self.center_stack, 1)

        self.settings_panel = SettingsPanel()
        effects.add_card_shadow(self.settings_panel)
        wrap.addWidget(self.settings_panel)

        # 状态 + 进度 + 动作单独占一排：挤在设置行尾会把「保存到」压得没地方，
        # 参数与动作分开也更符合阅读顺序（先选参数，再动手）
        self.action_row = QFrame()
        self.action_row.setProperty("role", "panel")
        effects.add_card_shadow(self.action_row)
        action_row = QHBoxLayout(self.action_row)
        action_row.setContentsMargins(12, 8, 12, 8)
        action_row.setSpacing(12)

        self.status_label = QLabel("就绪")
        self.status_label.setProperty("role", "hint")
        self.status_label.setMinimumWidth(150)
        self.status_label.setMaximumWidth(340)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedSize(QSize(220, 8))

        self.cancel_button = QPushButton("取消")
        self.cancel_button.setEnabled(False)
        self.start_button = QPushButton("开始处理")
        self.start_button.setProperty("role", "primary")
        self.start_button.setMinimumWidth(104)

        action_row.addWidget(self.status_label)
        action_row.addWidget(self.progress, 0, Qt.AlignVCenter)
        action_row.addStretch(1)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.start_button)
        wrap.addWidget(self.action_row)

        self.action_bar = FooterBar()
        effects.add_card_shadow(self.action_bar)
        wrap.addWidget(self.action_bar)

        self._build_actions()

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("toolbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 6, 0, 0)
        row.setSpacing(8)

        self.toolbar_add_files = QPushButton("添加图片")
        self.toolbar_add_folder = QPushButton("添加文件夹")
        self.toolbar_clear = QPushButton("清空列表")
        for button in (self.toolbar_add_files, self.toolbar_add_folder, self.toolbar_clear):
            row.addWidget(button)
        row.addStretch(1)

        self.toolbar_more = QPushButton("设置")
        self.toolbar_more.setProperty("role", "menubtn")
        self.toolbar_more.setToolTip("模型管理与关于")
        row.addWidget(self.toolbar_more)
        return bar

    def _build_actions(self) -> None:
        """动作对象挂在窗口上（不进菜单栏），菜单栏已去掉。

        菜单只保留「设置」这一个入口，快捷键照旧可用：QAction 直接挂在
        主窗口上，Qt 会为其注册窗口级快捷键。
        """
        self.action_add_files = QAction("添加图片…", self)
        self.action_add_files.setShortcut(QKeySequence("Ctrl+O"))
        self.action_add_folder = QAction("添加文件夹…", self)
        self.action_add_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.action_clear = QAction("清空列表", self)
        self.action_quit = QAction("退出", self)
        self.action_quit.setShortcut(QKeySequence("Ctrl+Q"))

        self.action_manage_models = QAction("模型管理…", self)
        self.action_manage_models.setShortcut(QKeySequence("Ctrl+M"))
        self.action_open_model_dir = QAction("打开模型目录", self)
        self.action_about = QAction("关于 PixTrace", self)

        for action in (
            self.action_add_files,
            self.action_add_folder,
            self.action_clear,
            self.action_quit,
            self.action_manage_models,
            self.action_open_model_dir,
            self.action_about,
        ):
            self.addAction(action)

        menu = QMenu(self)
        menu.addAction(self.action_manage_models)
        menu.addAction(self.action_open_model_dir)
        menu.addSeparator()
        menu.addAction(self.action_about)
        effects.add_popup_shadow(menu)
        self.toolbar_more.setMenu(menu)

    def _connect(self) -> None:
        self.toolbar_add_files.clicked.connect(self.pick_files)
        self.toolbar_add_folder.clicked.connect(self.pick_folder)
        self.toolbar_clear.clicked.connect(self.clear_all)

        self.action_add_files.triggered.connect(self.pick_files)
        self.action_add_folder.triggered.connect(self.pick_folder)
        self.action_clear.triggered.connect(self.clear_all)
        self.action_quit.triggered.connect(self.close)
        self.action_about.triggered.connect(self.show_about)
        self.action_manage_models.triggered.connect(self.open_model_manager)
        self.action_open_model_dir.triggered.connect(self.open_model_dir)

        self.start_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.cancel)
        self.action_bar.support_button.clicked.connect(self.show_support)

        self.tree.itemDoubleClicked.connect(self.open_preview)
        QShortcut(QKeySequence.Delete, self.tree, activated=self.remove_selected)

        self.drop_area.pick_requested.connect(self.pick_files)

        self.settings_panel.changed.connect(self._schedule_replan)

        self.controller.progressed.connect(self._on_progress)
        self.controller.finished.connect(self._on_finished)
        self.controller.failed.connect(self._on_failed)

    # ------------------------------------------------------- 兼容旧接口

    # ------------------------------------------------------------- 任务收集
    def pick_files(self) -> None:
        paths_list, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片",
            "",
            "图片 (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
        )
        if paths_list:
            self.add_inputs([Path(p) for p in paths_list])

    def pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if path:
            self.add_inputs([Path(path)])

    def add_inputs(self, paths_list: list[Path]) -> None:
        added = 0
        for path in paths_list:
            if path not in self._inputs:
                self._inputs.append(path)
                added += 1
        if added:
            self._replan()

    def remove_selected(self) -> None:
        if self.controller.is_running():
            return
        selected = {item.data(0, SRC_ROLE) for item in self.tree.selectedItems()}
        if not selected:
            return
        self._inputs = [p for p in self._inputs if str(p) not in selected]
        self._replan()

    def clear_all(self) -> None:
        if self.controller.is_running():
            return
        self._inputs.clear()
        self._tasks.clear()
        self._task_map.clear()
        self.tree.clear()
        self._rows.clear()
        self.progress.setValue(0)
        self._set_status("就绪")
        self._sync_center()
        self._update_hint()

    # --------------------------------------------------------------- 规划
    def _schedule_replan(self) -> None:
        if self.controller.is_running():
            return
        self._replan_timer.start()

    def _replan(self) -> None:
        if not self._inputs:
            self._tasks = []
            self._task_map = {}
            self._refresh_list()
            return

        try:
            options = self.settings_panel.build_options()
            self._tasks = build_tasks(self._inputs, options)
        except (FileNotFoundError, ValueError) as exc:
            self._tasks = []
            self._set_status(f"无法规划任务：{exc}")
        self._task_map = {str(t.src): t for t in self._tasks}
        self._refresh_list()

    def _refresh_list(self) -> None:
        self.tree.clear()
        self._rows.clear()

        for task in self._tasks:
            item = QTreeWidgetItem([str(task.rel), status_of(task), self._elapsed_text(task)])
            item.setData(0, SRC_ROLE, str(task.src))
            item.setSizeHint(0, QSize(0, ROW_HEIGHT))
            item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
            item.setFont(2, style.mono_font(12))  # 耗时用等宽字体，数字列才齐
            item.setForeground(1, _status_brush(task.status))
            item.setToolTip(0, f"源文件：{task.src}\n保存到：{task.dst}\n（双击查看对比）")
            if task.error:
                item.setToolTip(1, task.error)
            self.tree.addTopLevelItem(item)
            self._rows[str(task.src)] = item

        self._sync_center()
        self._update_hint()
        if self._tasks:
            self._set_status(f"共 {len(self._tasks)} 张待处理")

    def _sync_center(self) -> None:
        """没有输入就显示大拖拽区（此时 44px 提示条多余，一并隐藏）。"""
        empty = not self._inputs
        self.center_stack.setCurrentIndex(0 if empty else 1)
        self.dropbar.setVisible(not empty)

    def _update_hint(self) -> None:
        if not self._inputs:
            self.dropbar.set_message(DEFAULT_DROP_TITLE)
            self.drop_area.set_message(DEFAULT_DROP_TITLE, DEFAULT_DROP_HINT)
        elif not self._tasks:
            self.dropbar.set_message("未找到可处理的图片（支持 PNG / JPG / WebP / BMP / TIFF）")
            self.drop_area.set_message(
                "没找到可处理的图片",
                "支持 PNG / JPG / WebP / BMP / TIFF，换个文件夹或直接拖入图片文件",
            )
        else:
            self.dropbar.set_message("已就绪 · 还可以继续拖入图片或文件夹")

    @staticmethod
    def _elapsed_text(task: Task) -> str:
        if task.elapsed_ms <= 0:
            return "-"
        return f"{task.elapsed_ms / 1000:.2f}s"

    def _update_row(self, task: Task) -> None:
        item = self._rows.get(str(task.src))
        if item is None:
            return
        item.setText(1, status_of(task))
        item.setText(2, self._elapsed_text(task))
        item.setForeground(1, _status_brush(task.status))
        if task.error:
            item.setToolTip(1, task.error)

    # --------------------------------------------------------------- 执行
    def start(self) -> None:
        if self.controller.is_running():
            return
        if not self._inputs:
            QMessageBox.information(self, "还没有图片", "请先添加图片或文件夹。")
            return

        problem = self.settings_panel.validate()
        if problem:
            QMessageBox.warning(self, "设置不完整", problem)
            return

        options: JobOptions = self.settings_panel.build_options()

        try:
            spec = resolve_model(options.model_key)
        except KeyError as exc:
            QMessageBox.critical(self, "模型不可用", str(exc))
            return

        try:
            model_path = model_store.locate(spec.filename, spec.sha256)
        except FileNotFoundError:
            answer = QMessageBox.question(
                self,
                "模型尚未就绪",
                f"抠图模型（{spec.filename}）还没有就位。\n\n"
                "现在打开模型管理去下载，或从本地导入已下载的模型文件吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self.open_model_manager()
            return
        except RuntimeError as exc:
            QMessageBox.critical(self, "模型校验失败", f"{exc}\n\n可在「模型管理」里重新下载。")
            return

        try:
            self._tasks = build_tasks(self._inputs, options)
        except (FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(self, "无法规划任务", str(exc))
            return

        if not self._tasks:
            QMessageBox.information(self, "没有可处理的图片", "所选位置未找到支持的图片格式。")
            return

        self._task_map = {str(t.src): t for t in self._tasks}
        self._refresh_list()
        self.progress.setRange(0, len(self._tasks))
        self.progress.setValue(0)
        self._started_at = time.perf_counter()
        self._set_running(True)
        self._set_status("正在加载模型…")

        try:
            self.controller.start(
                self._tasks, spec, model_path, options, os.cpu_count() or 4
            )
        except RuntimeError as exc:
            self._set_running(False)
            QMessageBox.critical(self, "启动失败", str(exc))

    def cancel(self) -> None:
        if not self.controller.is_running():
            return
        self.controller.cancel()
        self.cancel_button.setEnabled(False)
        self._set_status("正在停止，等待当前图片处理完…")

    def _set_running(self, running: bool) -> None:
        self.settings_panel.set_running(running)
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        for widget in (self.toolbar_add_files, self.toolbar_add_folder, self.toolbar_clear):
            widget.setEnabled(not running)
        for action in (
            self.action_add_files,
            self.action_add_folder,
            self.action_clear,
            self.action_manage_models,
        ):
            action.setEnabled(not running)

    # --------------------------------------------------------------- 回调
    def _sync_task(self, task: Task) -> None:
        """把子进程返回的结果写回本地任务对象，避免列表与真实状态脱节。"""
        local = self._task_map.get(str(task.src))
        if local is not None:
            local.status = task.status
            local.elapsed_ms = task.elapsed_ms
            local.error = task.error

    def _on_progress(self, done: int, total: int, task: Task) -> None:
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)
        self._sync_task(task)
        self._update_row(task)

        elapsed = time.perf_counter() - self._started_at
        rate = elapsed / done if done else 0.0
        remaining = rate * (total - done)
        self._set_status(
            f"{done}/{total} · {rate:.2f}s/张 · 剩余约 {self._format_duration(remaining)}"
        )

    def _on_finished(self, report) -> None:
        self._set_running(False)
        self.progress.setValue(self.progress.maximum())
        self._set_status(
            f"完成 {report.done} · 失败 {report.failed}"
            f" · 总耗时 {report.elapsed_ms / 1000:.1f}s"
            f" · 平均 {report.avg_ms:.0f}ms/张"
        )

        if report.failed:
            preview = "\n".join(f"  {Path(p).name}：{err}" for p, err in report.failures[:8])
            more = "" if len(report.failures) <= 8 else f"\n  …以及另外 {len(report.failures) - 8} 个"
            QMessageBox.warning(
                self,
                "部分文件处理失败",
                f"{report.failed} 个文件失败：\n\n{preview}{more}\n\n"
                "列表里已标红，再次点击「开始处理」即可重跑（已成功的会跳过）。",
            )

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self._set_status("处理中断")
        QMessageBox.critical(self, "处理失败", message)

    # --------------------------------------------------------------- 其他
    def open_preview(self, item: QTreeWidgetItem, _column: int) -> None:
        src_text = item.data(0, SRC_ROLE)
        if not src_text:
            return
        src = Path(src_text)
        task = self._task_map.get(src_text)
        dst = None
        if task is not None and task.dst.exists():
            dst = task.dst
        PreviewWindow(src, dst, self).exec()

    def open_model_manager(self) -> None:
        if self.controller.is_running():
            return
        dialog = ModelManagerDialog(self, highlight_key=DEFAULT_MODEL_KEY)
        dialog.exec()
        self._sync_model_hint()

    def _sync_model_hint(self) -> None:
        """模型缺失时在状态栏给一句提示，不打断操作。"""
        if self.controller.is_running():
            return
        spec = resolve_model(DEFAULT_MODEL_KEY)
        if model_store.find_model(spec.filename) is None:
            self._set_status("抠图模型未就绪 — 按 Ctrl+M 打开模型管理")
        elif self.status_label.text().startswith("抠图模型未就绪"):
            self._set_status("就绪")

    def open_model_dir(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        directory = model_store.user_cache_dir()
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def show_about(self) -> None:
        logo = paths.resource_dir() / "assets" / "logo-full.png"
        logo_html = (
            f'<p><img src="{logo.as_posix()}" width="120"></p>' if logo.is_file() else ""
        )
        QMessageBox.about(
            self,
            "关于 PixTrace",
            logo_html
            + "<h3>PixTrace · 去背景</h3>"
            "<p>本地离线抠图，图片不联网、不上传。</p>"
            "<p><b>两个功能</b><br>"
            "1. 去掉背景，输出透明 PNG<br>"
            "2. 去掉背景后换成纯色底<br>"
            "结果默认保存在原图所在文件夹，文件名加 <code>-无背景</code> 后缀。</p>"
            "<p><b>模型</b><br>"
            "isnet-general-use（DIS，Apache-2.0），单张约 1.2 秒</p>"
            "<p><b>许可</b><br>本项目代码 MIT，第三方组件许可见 THIRD_PARTY_LICENSES.md</p>",
        )

    def show_support(self) -> None:
        """赞赏码弹窗：有 assets/support.png 就显示图片，否则显示占位提示。"""
        image = paths.resource_dir() / "assets" / "support.png"
        dialog = QDialog(self)
        dialog.setWindowTitle("赞赏")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        if image.is_file():
            picture = QLabel()
            picture.setPixmap(QPixmap(str(image)))
            picture.setAlignment(Qt.AlignCenter)
            layout.addWidget(picture)
        else:
            hint = QLabel(
                "赞赏码占位\n\n把赞赏码图片保存为程序目录下的\nassets/support.png，"
                "这里就会自动显示。"
            )
            hint.setAlignment(Qt.AlignCenter)
            layout.addWidget(hint)
        dialog.exec()

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setToolTip(text)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 1:
            return "不到 1 秒"
        if seconds < 60:
            return f"{seconds:.0f} 秒"
        minutes = seconds / 60
        if minutes < 60:
            return f"{minutes:.1f} 分钟"
        return f"{minutes / 60:.1f} 小时"

    # --------------------------------------------------------------- 拖拽
    def _set_drop_highlight(self, active: bool) -> None:
        self.dropbar.set_active(active)
        self.drop_area.set_active(active)
        self.tree.setProperty("dragover", "true" if active else "false")
        self.tree.style().unpolish(self.tree)
        self.tree.style().polish(self.tree)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and not self.controller.is_running():
            event.acceptProposedAction()
            self._set_drop_highlight(True)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._set_drop_highlight(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._set_drop_highlight(False)
        if self.controller.is_running():
            return
        paths_list = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local:
                path = Path(local)
                if path.exists():
                    paths_list.append(path)
        if paths_list:
            self.add_inputs(paths_list)
            event.acceptProposedAction()

    # --------------------------------------------------------- 配置持久化
    def _restore_state(self) -> None:
        # 键名带版本号：默认尺寸从 1080×720 收到 860×560 后，老记忆会把窗口
        # 又拉回大尺寸，所以在键名上翻一代（geometry → geometry2）让老值作废。
        # 用户此后的手动调整仍会被记住。
        if self._store.contains(LEGACY_GEOMETRY_KEY):
            self._store.remove(LEGACY_GEOMETRY_KEY)

        geometry = self._store.value(GEOMETRY_KEY)
        if geometry is not None:
            self.restoreGeometry(geometry)

        raw = self._store.value("panel/state_json")
        if isinstance(raw, str) and raw:
            try:
                state = json.loads(raw)
            except ValueError:
                state = None
            if isinstance(state, dict):
                self.settings_panel.restore(state)

        self._sync_model_hint()

    def _save_state(self) -> None:
        self._store.setValue(GEOMETRY_KEY, self.saveGeometry())
        self._store.setValue(
            "panel/state_json", json.dumps(self.settings_panel.state(), ensure_ascii=False)
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.controller.is_running():
            answer = QMessageBox.question(
                self,
                "任务尚未完成",
                "当前仍在处理中，要停止并退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.controller.cancel()

        self._save_state()
        event.accept()


def QSettings_store():
    from PySide6.QtCore import QSettings

    return QSettings("pixtrace", "pixtrace")
