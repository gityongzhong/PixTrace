"""基准测试：分离「模型加载」与「纯推理」耗时。

测两种场景，对应两类使用方式：
  single  默认线程数，测单张图的响应速度
  worker  intra_op=1，对应批量模式下每个工作进程的实际配置，
          吞吐量约等于 workers × 该数值的倒数
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.models import MODELS  # noqa: E402
from app.core.postprocess import normalize_mask, unletterbox  # noqa: E402
from app.core.preprocess import letterbox, to_tensor  # noqa: E402

SAMPLES = [
    ("人像 2582x3443", Path("C:/Users/Administrator/Pictures/我.jpg")),
    ("壁纸 3840x2400", Path("C:/Windows/Web/Wallpaper/ThemeA/img20.jpg")),
]

REPEATS = 7


def bench_session(model_path: Path, spec, intra_op: int | None) -> ort.InferenceSession:
    options = ort.SessionOptions()
    if intra_op is not None:
        options.intra_op_num_threads = intra_op
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.log_severity_level = 3

    started = time.perf_counter()
    session = ort.InferenceSession(str(model_path), sess_options=options, providers=["CPUExecutionProvider"])
    elapsed = (time.perf_counter() - started) * 1000
    print(f"  加载: {elapsed:.0f} ms")
    return session


def bench_inference(session: ort.InferenceSession, spec, img: Image.Image) -> float:
    canvas, meta = letterbox(img, spec.input_size)
    tensor = to_tensor(canvas, spec.mean, spec.std, spec.divide)
    feeds = {session.get_inputs()[0].name: tensor}
    out_name = session.get_outputs()[spec.output_index].name

    session.run([out_name], feeds)  # 预热

    timings = []
    for _ in range(REPEATS):
        started = time.perf_counter()
        raw = session.run([out_name], feeds)[0]
        timings.append((time.perf_counter() - started) * 1000)

    alpha = unletterbox(normalize_mask(np.squeeze(raw)), meta)
    coverage = float((alpha > 0.5).mean()) * 100
    return statistics.median(timings), coverage


def main() -> int:
    print(f"CPU: {__import__('os').cpu_count()} 核，每项重复 {REPEATS} 次取中位数\n")

    for spec in MODELS.values():
        print(f"=== {spec.display}档 {spec.filename} ===")
        for label, intra_op in (("single(默认线程)", None), ("worker(intra=1)", 1)):
            session = bench_session(ROOT / "models" / spec.filename, spec, intra_op)
            for sample_name, sample_path in SAMPLES:
                with Image.open(sample_path) as raw:
                    img = raw.convert("RGB")
                median_ms, coverage = bench_inference(session, spec, img)
                print(f"  {label:20s} {sample_name}: 推理 {median_ms:6.0f} ms  前景 {coverage:4.1f}%")
            del session
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
