"""批量调度。

用滑动窗口提交任务（在飞任务数上限为 进程数 × 4），而不是一次性把几万个
future 全塞进内存——处理十万张图时这点很重要。
"""

from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Callable, Iterable

from ..core.models import ModelSpec
from ..core.types import JobOptions, JobReport, Task, TaskStatus
from .worker import process_one, worker_init

ProgressFn = Callable[[int, int, Task], None]

_WINDOW_FACTOR = 4


def run_batch(
    tasks: list[Task],
    spec: ModelSpec,
    model_path: Path,
    options: JobOptions,
    workers: int,
    progress: ProgressFn | None = None,
    cancel_event=None,
) -> JobReport:
    """并发执行任务列表，返回汇总报告。

    cancel_event 为非阻塞事件对象（multiprocessing.Event 或 threading.Event）；
    置位后停止补充新任务，已在飞的任务会跑完。
    """
    report = JobReport(total=len(tasks))
    if not tasks:
        return report

    started = time.perf_counter()

    def _cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=worker_init,
        initargs=(spec, str(model_path), options),
    ) as pool:
        pending: dict = {}
        stream: Iterable[Task] = iter(tasks)

        def _fill() -> None:
            while len(pending) < workers * _WINDOW_FACTOR:
                if _cancelled():
                    return
                task = next(stream, None)
                if task is None:
                    return
                pending[pool.submit(process_one, task)] = task

        _fill()

        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                task = pending.pop(future)
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - 进程级崩溃
                    result = task
                    result.status = TaskStatus.FAILED
                    result.error = f"工作进程异常：{type(exc).__name__}: {exc}"[:300]

                _tally(report, result)
                if progress is not None:
                    progress(report.done + report.failed + report.skipped, report.total, result)

            if _cancelled():
                for future in pending:
                    future.cancel()
                break

            _fill()

        if _cancelled():
            pool.shutdown(wait=False, cancel_futures=True)

    report.elapsed_ms = int((time.perf_counter() - started) * 1000)
    return report


def _tally(report: JobReport, task: Task) -> None:
    if task.status is TaskStatus.DONE:
        report.done += 1
    elif task.status is TaskStatus.SKIPPED:
        report.skipped += 1
    else:
        report.failed += 1
        report.failures.append((task.src, task.error))
