"""模型管理对话框：查看两档模型的状态、下载、手动导入、配置下载源。

为什么需要一个独立对话框而不是「启动时静默下载」：
高精档 171MB，在受限网络下可能要几十分钟。这种事必须让用户看得见进度、
能取消、能换源、也能走完全离线的导入路径——而不是卡在启动画面上不知道发生了什么。
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..core.models import MODELS, ModelSpec
from ..infra import downloader, model_store
from ..infra.logging import get_logger
from . import style

COLUMNS = ("档位", "模型文件", "大小", "状态")
KEY_ROLE = Qt.UserRole
STATE_ROLE = Qt.UserRole + 1

# 界面上的大小提示（字节），仅用于未下载时给用户一个预期
SIZE_HINTS = {
    "u2netp": 4_574_861,
    "isnet-general-use": 178_648_008,
}

STATE_LABELS = {
    model_store.ModelState.READY: "已就绪",
    model_store.ModelState.MISSING: "未下载",
    model_store.ModelState.CORRUPT: "校验失败",
}

STATE_COLORS = {
    model_store.ModelState.READY: style.OK_TEXT,
    model_store.ModelState.MISSING: style.WARN_TEXT,
    model_store.ModelState.CORRUPT: style.ERR_TEXT,
}


class DownloadController(QObject):
    """把阻塞的下载放到后台线程，进度通过信号回主线程。"""

    progressed = Signal(object)  # downloader.Progress
    finished = Signal(object)  # downloader.DownloadResult
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        # 用显式标志而不是 thread.is_alive()：线程结束与主线程处理完成信号之间
        # 有一小段窗口，靠 is_alive() 判断会让按钮状态陷入「永远禁用」。
        self._active = False

    def is_running(self) -> bool:
        return self._active

    def start(self, spec: ModelSpec) -> None:
        if self._active:
            raise RuntimeError("已有下载任务在进行")
        self._cancel = threading.Event()
        self._active = True
        self._thread = threading.Thread(
            target=self._run, args=(spec,), daemon=True, name="pixtrace-download"
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def _run(self, spec: ModelSpec) -> None:
        logger = get_logger()
        try:
            result = downloader.fetch_model(
                spec,
                progress=self.progressed.emit,
                cancelled=self._cancel.is_set,
                on_source=lambda url: logger.info("下载源：%s", url),
            )
        except downloader.DownloadCancelled:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001 - 兜底，避免线程静默死掉
            if self._cancel.is_set():
                self.cancelled.emit()
            else:
                logger.error("模型下载失败：%s", exc, exc_info=True)
                self.failed.emit(str(exc))
        else:
            self.finished.emit(result)
        finally:
            self._active = False


class ModelManagerDialog(QDialog):
    """models_changed 在模型文件状态发生变化后发出，供主窗口刷新。"""

    models_changed = Signal()

    def __init__(self, parent=None, highlight_key: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("模型管理")
        self.setMinimumSize(680, 420)

        self._states: dict[str, str] = {}
        self._paths: dict[str, Path | None] = {}
        self._selected_key: str | None = highlight_key
        self.controller = DownloadController(self)

        self._build()
        self._connect()
        self.refresh(highlight_key=highlight_key)

    # ------------------------------------------------------------- 构建
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("模型文件")
        title.setProperty("role", "section")
        root.addWidget(title)

        hint = QLabel(
            "极速档随安装包提供，通常已就绪；高精档按需下载。"
            "下载的文件放在用户数据目录，不写安装目录。"
        )
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(list(COLUMNS))
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.tree.setColumnWidth(0, 90)
        self.tree.setColumnWidth(2, 90)
        self.tree.setColumnWidth(3, 100)
        self.tree.setMinimumHeight(140)
        root.addWidget(self.tree, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.detail = QLabel("")
        self.detail.setProperty("role", "hint")
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.detail)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.download_button = QPushButton("下载")
        self.download_button.setProperty("role", "primary")
        self.import_button = QPushButton("手动导入…")
        self.open_dir_button = QPushButton("打开模型目录")
        self.source_button = QPushButton("设置下载源…")
        self.close_button = QPushButton("关闭")
        for widget in (
            self.download_button,
            self.import_button,
            self.open_dir_button,
            self.source_button,
        ):
            buttons.addWidget(widget)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        root.addLayout(buttons)

    def _connect(self) -> None:
        self.tree.currentItemChanged.connect(lambda *_: self._sync_buttons())
        self.tree.itemDoubleClicked.connect(lambda *_: self.start_download())
        self.download_button.clicked.connect(self._on_primary_clicked)
        self.import_button.clicked.connect(self.import_model)
        self.open_dir_button.clicked.connect(self.open_model_dir)
        self.source_button.clicked.connect(self.edit_source)
        self.close_button.clicked.connect(self.reject)

        self.controller.progressed.connect(self._on_progress)
        self.controller.finished.connect(self._on_finished)
        self.controller.failed.connect(self._on_failed)
        self.controller.cancelled.connect(self._on_cancelled)

    # ------------------------------------------------------------- 状态
    def refresh(self, *, highlight_key: str | None = None) -> None:
        """重新探测全部模型状态并重建列表。"""
        selected = highlight_key or self._selected_key
        self.tree.clear()
        self._states.clear()
        self._paths.clear()

        for spec in MODELS.values():
            state, path, detail = model_store.inspect(spec.filename, spec.sha256)
            self._states[spec.key] = state
            self._paths[spec.key] = path

            size_bytes = path.stat().st_size if path and path.is_file() else SIZE_HINTS.get(spec.key, 0)
            item = QTreeWidgetItem(
                [spec.display, spec.filename, downloader.human_size(size_bytes), STATE_LABELS[state]]
            )
            item.setData(0, KEY_ROLE, spec.key)
            item.setData(0, STATE_ROLE, state)
            item.setForeground(3, QBrush(QColor(STATE_COLORS[state])))
            tip = [f"档位：{spec.display}", f"输入尺寸：{spec.input_size}×{spec.input_size}"]
            if path:
                tip.append(f"位置：{path}")
            if detail:
                tip.append(detail)
            item.setToolTip(1, "\n".join(tip))
            self.tree.addTopLevelItem(item)

        target_row = 0
        for row in range(self.tree.topLevelItemCount()):
            if self.tree.topLevelItem(row).data(0, KEY_ROLE) == selected:
                target_row = row
                break
        self.tree.setCurrentItem(self.tree.topLevelItem(target_row))

        self._show_search_paths()
        self._sync_buttons()

    def _show_search_paths(self) -> None:
        if self.controller.is_running():
            return
        dirs = "、".join(str(d) for d in model_store.search_dirs())
        self.detail.setText(f"模型查找顺序：{dirs}")

    def _current_key(self) -> str | None:
        item = self.tree.currentItem()
        return item.data(0, KEY_ROLE) if item else None

    def _current_spec(self) -> ModelSpec | None:
        key = self._current_key()
        return MODELS.get(key) if key else None

    def _sync_buttons(self) -> None:
        if self.controller.is_running():
            return
        key = self._current_key()
        state = self._states.get(key or "", model_store.ModelState.MISSING)
        self.download_button.setText("重新下载" if state == model_store.ModelState.CORRUPT else "下载")
        self.download_button.setEnabled(state != model_store.ModelState.READY)
        self.import_button.setEnabled(True)
        self.source_button.setEnabled(True)

    # ------------------------------------------------------------- 下载
    def _on_primary_clicked(self) -> None:
        """主按钮一个位置承担「下载」与「取消下载」两种语义。"""
        if self.controller.is_running():
            self.controller.cancel()
            self.detail.setText("正在取消…")
        else:
            self.start_download()

    def start_download(self) -> None:
        if self.controller.is_running():
            return
        spec = self._current_spec()
        if spec is None:
            return
        if self._states.get(spec.key) == model_store.ModelState.READY:
            return

        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.detail.setText(f"正在下载 {spec.filename}…")
        self._set_busy(True)
        try:
            self.controller.start(spec)
        except RuntimeError as exc:
            self._set_busy(False)
            QMessageBox.warning(self, "无法开始下载", str(exc))

    def _set_busy(self, busy: bool) -> None:
        self.tree.setEnabled(not busy)
        self.import_button.setEnabled(not busy)
        self.source_button.setEnabled(not busy)
        self.download_button.setEnabled(True)
        if busy:
            self.download_button.setText("取消下载")
        else:
            self.download_button.setText("下载")
            self._sync_buttons()

    def _on_progress(self, progress) -> None:
        self.progress.setValue(int(progress.fraction * 1000))
        eta = progress.eta_s
        eta_text = ""
        if eta is not None and eta > 0:
            eta_text = f" · 剩余约 {eta:.0f} 秒"
        self.detail.setText(
            f"{progress.fraction * 100:.1f}%  "
            f"{downloader.human_size(progress.downloaded)} / {downloader.human_size(progress.total)}"
            f"  ·  {downloader.human_size(progress.speed_bps)}/s{eta_text}"
            + (f"  ·  已续传 {downloader.human_size(progress.resumed_from)}" if progress.resumed_from else "")
        )

    def _on_finished(self, result) -> None:
        self._set_busy(False)
        self.progress.setVisible(False)
        self.detail.setText(
            f"完成：{result.path.name}  {downloader.human_size(result.bytes_written)}"
            f"  用时 {result.elapsed_s:.0f} 秒  校验通过"
        )
        self.refresh()
        self.models_changed.emit()

    def _on_failed(self, message: str) -> None:
        self._set_busy(False)
        self.progress.setVisible(False)
        self.detail.setText("下载失败")
        self.refresh()
        QMessageBox.critical(self, "下载失败", message)

    def _on_cancelled(self) -> None:
        self._set_busy(False)
        self.progress.setVisible(False)
        self.detail.setText("已取消。已下载的分片会保留，下次继续。")
        self.refresh()

    # --------------------------------------------------------- 手动导入
    def import_model(self) -> None:
        """从本地选择 .onnx 文件导入。

        先按文件名匹配档位，文件名对不上再按 sha256 反查——
        用户常把文件改名成 "model.onnx"，只认文件名会让这条路走不通。
        """
        path_text, _ = QFileDialog.getOpenFileName(
            self, "选择模型文件", "", "ONNX 模型 (*.onnx);;所有文件 (*)"
        )
        if not path_text:
            return
        source = Path(path_text)
        if not source.is_file():
            QMessageBox.warning(self, "文件不存在", str(source))
            return

        spec = self._identify_spec(source)
        if spec is None:
            QMessageBox.warning(
                self,
                "无法识别模型",
                "该文件的文件名与 sha256 都与已知模型不匹配。\n\n"
                "本程序只接受以下模型：\n"
                + "\n".join(f"  · {s.filename}（{s.display}档）" for s in MODELS.values()),
            )
            return

        actual = model_store.sha256_of(source)
        if actual.lower() != spec.sha256.lower():
            QMessageBox.warning(
                self,
                "校验失败",
                f"文件内容与该档位不匹配，可能下载不完整或不是同一个模型。\n\n"
                f"期望 sha256：{spec.sha256[:32]}…\n实际 sha256：{actual[:32]}…",
            )
            return

        target_dir = model_store.user_cache_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / spec.filename
        try:
            if source.resolve() != target.resolve():
                shutil.copy2(source, target)
        except OSError as exc:
            QMessageBox.critical(self, "导入失败", f"无法写入 {target}：\n{exc}")
            return

        self.detail.setText(f"已导入 {spec.display}档：{target}")
        self.refresh(highlight_key=spec.key)
        self.models_changed.emit()

    def _identify_spec(self, source: Path) -> ModelSpec | None:
        by_name = next((s for s in MODELS.values() if s.filename == source.name), None)
        if by_name is not None:
            return by_name
        digest = model_store.sha256_of(source).lower()
        return next((s for s in MODELS.values() if s.sha256.lower() == digest), None)

    # ------------------------------------------------------- 目录与下载源
    def open_model_dir(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        key = self._current_key()
        found = self._paths.get(key or "")
        directory = found.parent if found else model_store.user_cache_dir()
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def edit_source(self) -> None:
        current = downloader.mirror_prefix()
        hint = (
            "填写镜像前缀，下载时会优先尝试「前缀 + 官方地址」。\n"
            "例如 ghproxy 类镜像填 https://ghfast.top/ ；留空表示只用官方地址。\n\n"
            "当前前缀："
        )
        text, ok = QInputDialog.getText(
            self, "设置下载源", hint + (current or "（未设置）"), text=current
        )
        if not ok:
            return
        prefix = text.strip()
        try:
            downloader.save_source_config({"mirror_prefix": prefix} if prefix else {})
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", f"无法写入配置：\n{exc}")
            return
        self.detail.setText(f"下载源已更新：{prefix or '仅使用官方地址'}")
