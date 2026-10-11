"""命令行入口。

单图:
    python cli.py 照片.jpg                    结果与照片并排（照片-无背景.png）
    python cli.py 照片.jpg -b color --color 255,0,0

批量:
    python cli.py 图片目录/ --alongside        结果与原图并排
    python cli.py 图片目录/ -o 输出目录/        结果另存，保留子目录结构
    python cli.py 图片目录/                    结果进同级 _PixTrace/（CLI 默认，不污染原图目录）

注意：必须在 if __name__ == "__main__" 里调用 main()，
Windows 的进程池以 spawn 方式启动，会重新导入本模块。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.batch.job_queue import run_batch  # noqa: E402
from app.batch.planner import build_tasks, resolve_workers  # noqa: E402
from app.batch.worker import process_one, worker_init  # noqa: E402
from app.core.models import resolve_model  # noqa: E402
from app.core.types import (  # noqa: E402
    BackgroundKind,
    BackgroundSpec,
    JobOptions,
    JobReport,
    OutputFormat,
    Task,
    TaskStatus,
)
from app.infra import model_store  # noqa: E402
from app.infra.logging import setup_logging  # noqa: E402

MAX_PRINTED_FAILURES = 20


def parse_color(text: str) -> tuple[int, int, int]:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("颜色格式应为 R,G,B，例如 255,255,255")
    try:
        rgb = tuple(int(p) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("颜色分量必须是整数") from exc
    if any(not 0 <= v <= 255 for v in rgb):
        raise argparse.ArgumentTypeError("颜色分量必须在 0-255 之间")
    return rgb  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pixtrace",
        description="本地离线批量抠图：去背景、替换背景，全程不上传图片。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python cli.py 照片.jpg                            单图，输出到原图所在文件夹
  python cli.py 照片.jpg -b color --color 255,0,0    换成红底
  python cli.py 图片夹/ --alongside                  批量，结果与原图并排
  python cli.py 图片夹/ -o 输出目录/                  批量，结果另存到指定目录
  python cli.py 照片.jpg -m fast                     极速档（320px，批量前预览用）
""",
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="图片文件或目录，可混合多个")
    parser.add_argument(
        "-m", "--model", default="quality", choices=["fast", "quality"],
        help="模型档位：quality=高精(1024px，默认) fast=极速(320px)",
    )
    parser.add_argument(
        "-f", "--format", dest="fmt", default="png", choices=["png", "webp", "jpg"],
        help="输出格式，默认 png",
    )
    parser.add_argument(
        "-b", "--bg", default="transparent",
        choices=["transparent", "color", "image", "blur"],
        help="背景：transparent=透明 color=纯色 image=贴图 blur=原图虚化",
    )
    parser.add_argument("--color", type=parse_color, default=(255, 255, 255), metavar="R,G,B",
                        help="纯色背景 RGB，默认 255,255,255")
    parser.add_argument("--bg-image", type=Path, default=None, help="背景贴图路径，配合 -b image")
    parser.add_argument("--darken", type=float, default=0.0, metavar="0~1",
                        help="blur 背景的压暗程度")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="输出目录（批量保留结构）；单文件输入时若以图片后缀结尾则视为输出文件名")
    parser.add_argument("--flat", action="store_true", help="批量时不保留子目录结构")
    parser.add_argument("--alongside", action="store_true",
                        help="输出到原图所在文件夹（文件名加 -无背景 后缀），与界面默认一致")
    parser.add_argument("--workers", type=int, default=0, help="并发进程数，默认按档位自动")
    parser.add_argument("--feather", type=float, default=0.0, help="遮罩边缘羽化半径（像素）")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的输出文件")
    parser.add_argument("--jpeg-quality", type=int, default=92, help="JPEG/WebP 质量，默认 92")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出调试日志")
    return parser


def make_options(args: argparse.Namespace) -> tuple[JobOptions, Path | None]:
    """返回 (作业参数, 单文件输出路径或 None)。"""
    background = BackgroundSpec(
        kind=BackgroundKind(args.bg),
        color=args.color,
        image_path=args.bg_image,
        darken=args.darken,
    )

    output_dir = args.output
    single_output_file: Path | None = None
    if (
        output_dir is not None
        and len(args.inputs) == 1
        and args.inputs[0].expanduser().is_file()
        and output_dir.suffix.lower() in {".png", ".webp", ".jpg"}
    ):
        single_output_file = output_dir
        output_dir = output_dir.parent

    options = JobOptions(
        model_key=args.model,
        output_format=OutputFormat(args.fmt),
        background=background,
        output_dir=output_dir,
        keep_structure=not args.flat,
        alongside=bool(args.alongside),
        workers=args.workers,
        feather=args.feather,
        overwrite=args.overwrite,
        jpeg_quality=args.jpeg_quality,
    )
    return options, single_output_file


def run_single(tasks: list[Task], spec, model_path: Path, options: JobOptions) -> JobReport:
    """单张图在主进程直接跑：省掉进程池启动 + 模型二次加载的开销。"""
    report = JobReport(total=len(tasks))
    started = time.perf_counter()
    worker_init(spec, str(model_path), options)
    for task in tasks:
        result = process_one(task)
        if result.status is TaskStatus.DONE:
            report.done += 1
        elif result.status is TaskStatus.SKIPPED:
            report.skipped += 1
        else:
            report.failed += 1
            report.failures.append((result.src, result.error))
    report.elapsed_ms = int((time.perf_counter() - started) * 1000)
    return report


def print_progress(done: int, total: int, task: Task) -> None:
    pct = done / total * 100 if total else 100.0
    flag = {TaskStatus.DONE: "", TaskStatus.SKIPPED: " [跳过]"}.get(task.status, " [失败]")
    print(f"\r  {done}/{total} ({pct:4.1f}%){flag}   ", end="", flush=True)


def print_report(report: JobReport) -> None:
    print()
    seconds = report.elapsed_ms / 1000
    print(f"完成 {report.done}  跳过 {report.skipped}  失败 {report.failed}  "
          f"耗时 {seconds:.1f}s  平均 {report.avg_ms:.0f}ms/张")

    if report.failures:
        print("\n失败清单：")
        for src, error in report.failures[:MAX_PRINTED_FAILURES]:
            print(f"  {src.name}  <-  {error}")
        remaining = len(report.failures) - MAX_PRINTED_FAILURES
        if remaining > 0:
            print(f"  ...以及另外 {remaining} 条")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)

    try:
        spec = resolve_model(args.model)
        model_path = model_store.locate(spec.filename, spec.sha256)
        options, single_output_file = make_options(args)
        inputs = [p.expanduser() for p in args.inputs]
        tasks = build_tasks(inputs, options)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if single_output_file is not None and len(tasks) == 1:
        tasks[0].dst = single_output_file

    print(f"模型：{spec.display}档 {spec.filename}（输入 {spec.input_size}px）")
    print(f"任务：{len(tasks)} 张，输出格式 {options.output_format.value.upper()}")

    if len(tasks) == 1:
        report = run_single(tasks, spec, model_path, options)
    else:
        workers = resolve_workers(spec.workers_hint, options.workers, os.cpu_count() or 4)
        print(f"并发：{workers} 进程")
        report = run_batch(tasks, spec, model_path, options, workers, progress=print_progress)

    print_report(report)
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
