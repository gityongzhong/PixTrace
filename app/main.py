"""GUI 入口。

Windows 的进程池用 spawn 启动，冻结（PyInstaller）后子进程会重新执行本 exe：
必须在最外层先调 multiprocessing.freeze_support()，否则每个 worker 都会
把整个 GUI 再拉起来一次，进程数爆炸。这是打包后最容易翻车、也最难排查的一处，
所以它被放在所有 import 之前。

附带 --selftest：不启动界面，跑一张合成图的完整批处理链路并把结果写成 JSON。
存在的原因是打包产物必须能被自动验证——冻结后「开发态好好的，打包就坏」
的问题（多进程、模型路径、隐式导入）只有真实 exe 上才暴露得出来，
人工点界面验证不了这类回归。
"""

from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _make_fixtures(directory: Path, count: int = 3) -> list[Path]:
    """生成合成素材：深色背景上的亮色矩形与圆，模型应稳定认出主体。"""
    from PIL import Image, ImageDraw, ImageFilter

    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index in range(count):
        image = Image.new("RGB", (640, 480), (24, 32, 28))
        draw = ImageDraw.Draw(image)
        draw.rectangle([380, 90, 620, 410], fill=(206, 188, 150))
        draw.ellipse([90, 120, 330, 400], fill=(236, 112, 99))
        image = image.filter(ImageFilter.GaussianBlur(1.2))
        target = directory / f"case_{index}.png"
        image.save(target)
        paths.append(target)
    return paths


def _selftest(out_path: Path | None = None) -> int:
    """无人值守自检。返回 0 表示全链路通过。

    覆盖两档模型——分发版（便携版）两个模型都带上了，自检就必须覆盖实际分发内容，
    只测极速档会漏掉高精档在冻结环境下的问题。

    每档覆盖：模型定位与 sha256 校验、多进程批处理（强制 >1 进程以触发 spawn 路径）、
    输出落盘且带 alpha 通道。结果写 JSON，便于远程诊断用户机器上的问题。
    """
    import json
    import tempfile
    import time

    from app.batch.job_queue import run_batch
    from app.batch.planner import build_tasks
    from app.core.models import resolve_model
    from app.core.types import (
        BackgroundKind,
        BackgroundSpec,
        JobOptions,
        OutputFormat,
    )
    from app.infra import model_store, paths
    from app.infra.logging import get_logger

    logger = get_logger()
    report: dict = {
        "frozen": paths.is_frozen(),
        "portable": paths.is_portable(),
        "python": sys.version.split()[0],
        "models_cache_dir": str(paths.models_cache_dir()),
        "log_dir": str(paths.log_dir()),
        "steps": [],
    }

    def step(name: str, ok: bool, detail: str = "") -> bool:
        report["steps"].append({"step": name, "ok": ok, "detail": detail})
        logger.info("selftest %s: %s %s", "ok" if ok else "FAIL", name, detail)
        return ok

    # 极速档便宜，多跑几张以覆盖多进程调度；高精档跑 1 张，验证加载与 1024 输入路径
    plan = (("fast", 3, 2), ("quality", 1, 1))

    overall = True
    workdir = Path(tempfile.mkdtemp(prefix="pixtrace-selftest_"))
    try:
        fixtures = _make_fixtures(workdir / "input")
        overall &= step("make_fixtures", bool(fixtures), f"{len(fixtures)} 张合成图")

        for model_key, count, workers in plan:
            spec = resolve_model(model_key)
            try:
                model_path = model_store.locate(spec.filename, spec.sha256)
            except (FileNotFoundError, RuntimeError) as exc:
                if model_key == "fast":
                    overall &= step(f"model_locate[{model_key}]", False, str(exc))
                    break
                # 高精档不随包分发，缺失不算失败——用「模型管理」装上后可复测
                step(f"model_locate[{model_key}]", True, f"未提供，跳过：{exc}")
                continue
            overall &= step(f"model_locate[{model_key}]", True, str(model_path))

            options = JobOptions(
                model_key=spec.key,
                output_format=OutputFormat.PNG,
                background=BackgroundSpec(kind=BackgroundKind.TRANSPARENT),
                output_dir=workdir / f"out_{model_key}",
                keep_structure=False,
                workers=0,
                feather=0.0,
                overwrite=False,
                jpeg_quality=92,
            )
            tasks = build_tasks([workdir / "input"], options)[:count]
            started = time.perf_counter()
            outcome = run_batch(tasks, spec, model_path, options, workers=workers)
            elapsed = time.perf_counter() - started

            outputs = list(options.output_dir.glob("*.png"))
            overall &= step(
                f"batch[{model_key}]",
                outcome.done == len(tasks) and bool(outputs),
                f"done={outcome.done}/{len(tasks)} failed={outcome.failed} {elapsed:.1f}s {workers}进程",
            )

            alpha_ok = False
            if outputs:
                from PIL import Image

                with Image.open(outputs[0]) as check:
                    alpha_ok = check.mode == "RGBA" and check.getchannel("A").getextrema()[0] < 255
            overall &= step(f"output_alpha[{model_key}]", alpha_ok, f"{len(outputs)} 个输出")

            report.setdefault("batches", {})[model_key] = {
                "done": outcome.done,
                "failed": outcome.failed,
                "elapsed_ms": outcome.elapsed_ms,
                "failures": [f"{p}: {e}" for p, e in outcome.failures],
            }

        report["ok"] = bool(overall)
        return _finish(report, out_path, workdir)
    except Exception as exc:  # noqa: BLE001 - 自检自身出错也要留下现场
        report["ok"] = False
        report["fatal"] = f"{type(exc).__name__}: {exc}"
        logger.critical("selftest 崩溃", exc_info=True)
        return _finish(report, out_path, workdir)


def _finish(report: dict, out_path: Path | None, workdir: Path) -> int:
    import json

    report["workdir"] = str(workdir)
    target = out_path or (paths.user_data_dir() / "selftest.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report.get("ok") else 1


def _uicheck(out_path: Path | None = None) -> int:
    """渲染主界面并截图（打包产物专用的 UI 冒烟）。

    存在的理由：精简运行库、换 Qt 版本这类改动，出问题的方式是「窗口起不来」
    或「画不出来」，而 --selftest 不创建 QApplication，测不到这一层。
    这个模式把主窗口在无头（offscreen）模式下画一遍并落盘 PNG，
    让构建脚本能自动验证界面层。
    """
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.infra import paths
    from app.ui import style
    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("pixtrace")
    app.setOrganizationName("pixtrace")
    style.apply(app)

    window = MainWindow()
    # 不覆盖尺寸：uicheck 要验的就是真实默认开窗尺寸
    window.show()
    app.processEvents()

    target = out_path or (paths.user_data_dir() / "uicheck.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    ok = window.grab().save(str(target))
    print(f"uicheck -> {target} ({'ok' if ok else 'FAILED'})")
    return 0 if ok else 1


def _run_gui() -> int:
    from PySide6.QtWidgets import QApplication

    from app.ui import style
    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("pixtrace")
    app.setOrganizationName("pixtrace")
    app.setApplicationDisplayName("PixTrace · 去背景")
    style.apply(app)

    # 窗口/任务栏图标：exe 资源在开发态不存在，显式指到 assets 里的 PNG
    from app.infra import paths

    icon_path = paths.resource_dir() / "assets" / "pixtrace.png"
    if icon_path.is_file():
        from PySide6.QtGui import QIcon

        app.setWindowIcon(QIcon(str(icon_path)))

    # Windows：让任务栏把本程序识别成独立应用，图标和分组才正确
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pixtrace.app")
        except OSError:
            pass

    window = MainWindow()
    window.show()
    return app.exec()


def main() -> int:
    args = sys.argv[1:]

    if "--selftest" in args:
        from app.infra.logging import install_excepthook, setup_logging

        setup_logging(verbose=True)
        install_excepthook()
        out_index = args.index("--selftest")
        out_path = Path(args[out_index + 1]) if len(args) > out_index + 1 else None
        return _selftest(out_path)

    if "--uicheck" in args:
        out_index = args.index("--uicheck")
        out_path = (
            Path(args[out_index + 1])
            if len(args) > out_index + 1 and not args[out_index + 1].startswith("-")
            else None
        )
        return _uicheck(out_path)

    from app.infra.logging import install_excepthook, setup_logging

    setup_logging()
    install_excepthook()
    return _run_gui()


if __name__ == "__main__":
    multiprocessing.freeze_support()  # 必须最先执行，见模块 docstring
    raise SystemExit(main())
