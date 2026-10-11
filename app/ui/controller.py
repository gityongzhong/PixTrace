"""批处理控制器：把阻塞的 run_batch 放到后台线程，通过 Qt 信号回主线程。

用 threading.Thread 而不是 QThread：run_batch 是纯 Python 逻辑，不需要 Qt 事件循环；
Qt 的跨线程信号发射（queued connection）本身就是线程安全的。
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..batch.job_queue import run_batch
from ..batch.planner import resolve_workers
from ..core.models import ModelSpec
from ..core.types import JobOptions, JobReport, Task, TaskStatus


class BatchController(QObject):
    """一次只跑一个作业；start 前需确认 is_running() 为 False。"""

    # done, total, 当前任务
    progressed = Signal(int, int, object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        tasks: list[Task],
        spec: ModelSpec,
        model_path: Path,
        options: JobOptions,
        cpu_count: int,
    ) -> None:
        if self.is_running():
            raise RuntimeError("已有作业正在运行")

        workers = resolve_workers(spec.workers_hint, options.workers, cpu_count)
        self._cancel = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            args=(tasks, spec, model_path, options, workers),
            daemon=True,
            name="pixtrace-batch",
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def _run(self, tasks, spec, model_path, options, workers) -> None:
        try:
            report = run_batch(
                tasks,
                spec,
                model_path,
                options,
                workers,
                progress=self._emit_progress,
                cancel_event=self._cancel,
            )
        except Exception as exc:  # noqa: BLE001 - 兜底，避免线程静默死掉
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.finished.emit(report)

    def _emit_progress(self, done: int, total: int, task: Task) -> None:
        self.progressed.emit(done, total, task)


def status_of(task: Task) -> str:
    return {
        TaskStatus.PENDING: "等待",
        TaskStatus.DONE: "完成",
        TaskStatus.SKIPPED: "跳过",
        TaskStatus.FAILED: "失败",
    }.get(task.status, "等待")
