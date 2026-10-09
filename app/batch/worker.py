"""工作进程。

并发单位是进程，每个进程持有一个 InferenceEngine。每个模型档位的
intra_op 线程数由 ModelSpec.worker_intra 决定（实测基准见 models.py 注释）：
小模型配单线程 + 多进程，大模型保留默认多线程 + 少进程。

所有异常都在这里被吞掉并转成 Task.status，避免单个坏文件打断整个批次。
"""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image, ImageOps

from ..core.compositor import build_foreground, compose
from ..core.engine import InferenceEngine
from ..core.models import ModelSpec
from ..core.types import JobOptions, OutputFormat, Task, TaskStatus

_ENGINE: InferenceEngine | None = None
_OPTIONS: JobOptions | None = None


def worker_init(spec: ModelSpec, model_path: str, options: JobOptions) -> None:
    """进程池 initializer：模型只加载一次，之后所有任务复用。"""
    global _ENGINE, _OPTIONS
    _OPTIONS = options
    _ENGINE = InferenceEngine(spec, Path(model_path), intra_op_threads=spec.worker_intra)


def _save(img: Image.Image, dst: Path, options: JobOptions) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    fmt = options.output_format
    if fmt is OutputFormat.JPEG and img.mode != "RGB":
        img = img.convert("RGB")

    if fmt is OutputFormat.PNG:
        img.save(dst, format="PNG", compress_level=6)
    elif fmt is OutputFormat.WEBP:
        img.save(dst, format="WEBP", quality=options.jpeg_quality, method=4)
    elif fmt is OutputFormat.JPEG:
        img.save(dst, format="JPEG", quality=options.jpeg_quality, optimize=True, progressive=True)
    else:
        raise ValueError(f"未知输出格式：{fmt}")


def process_one(task: Task) -> Task:
    assert _ENGINE is not None and _OPTIONS is not None, "worker_init 未执行"

    started = time.perf_counter()
    try:
        if task.dst.exists() and not _OPTIONS.overwrite:
            task.status = TaskStatus.SKIPPED
            task.error = "目标文件已存在"
            return task

        # exif_transpose：手机拍摄的照片方向信息在 EXIF 里，
        # 不处理会导致遮罩与图像内容错位
        with Image.open(task.src) as raw:
            rgb = ImageOps.exif_transpose(raw).convert("RGB")

            mask = _ENGINE.predict_mask(rgb, feather=_OPTIONS.feather)
            foreground = build_foreground(rgb, mask)
            result = compose(foreground, _OPTIONS.background, rgb, _OPTIONS.output_format)

            _save(result, task.dst, _OPTIONS)

        task.status = TaskStatus.DONE
    except Exception as exc:  # noqa: BLE001 - 单文件失败不应打断批次
        task.status = TaskStatus.FAILED
        task.error = f"{type(exc).__name__}: {exc}"[:300]

    task.elapsed_ms = int((time.perf_counter() - started) * 1000)
    return task
