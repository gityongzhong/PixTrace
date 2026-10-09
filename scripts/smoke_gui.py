"""GUI 冒烟测试：真实跑两轮处理，验证 线程 + 进程池 + 信号回传 + 输出落点。

两轮分别覆盖界面的两个功能与两种保存位置：
  第一轮：透明背景，保存到「原图所在文件夹」（默认）→ 期望 *-无背景.png 出现在素材目录
  第二轮：纯色背景，保存到指定文件夹 → 期望输出落在指定目录

素材先复制到临时目录，避免往系统壁纸目录里写产物。

用法：python scripts/smoke_gui.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / ".shots"
SMOKE_IN = OUT_DIR / "smoke_in"
SMOKE_OUT = OUT_DIR / "smoke_out"

WALLPAPERS = [
    Path("C:/Windows/Web/Wallpaper/ThemeA/img20.jpg"),
    Path("C:/Windows/Web/Wallpaper/ThemeA/img21.jpg"),
    Path("C:/Windows/Web/Wallpaper/ThemeB/img24.jpg"),
]

MARKER = "-无背景"


def main() -> int:
    from PySide6.QtCore import QSettings, QTimer
    from PySide6.QtWidgets import QApplication

    from app.ui import style
    from app.ui.main_window import MainWindow

    # 必须测「默认状态」：清掉 QSettings 里的参数记忆，否则上一轮运行的
    # 背景/保存位置偏好会渗进来，测试结果失真
    store = QSettings("pixtrace", "pixtrace")
    store.remove("panel/state_json")
    store.remove("panel/state")
    store.sync()

    for directory in (SMOKE_IN, SMOKE_OUT):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

    sources = [p for p in WALLPAPERS if p.exists()]
    if not sources:
        print("没有可用素材")
        return 1
    for src in sources:
        shutil.copy2(src, SMOKE_IN / src.name)

    app = QApplication(sys.argv)
    style.apply(app)

    window = MainWindow()
    window.resize(1080, 720)
    window.show()

    state = {"round": 1}
    failures: list[str] = []

    def begin() -> None:
        window.add_inputs([SMOKE_IN])
        print(f"—— 第 1 轮：透明背景，保存到原图所在文件夹（{SMOKE_IN}）")
        window.start()

    def check(round_no: int) -> bool:
        if window.controller.is_running():
            return False

        if round_no == 1:
            produced = sorted(SMOKE_IN.glob(f"*{MARKER}.png"))
            print(f"  输出 {len(produced)} / 期望 {len(sources)}")
            for path in produced:
                print(f"    {path.name}  {path.stat().st_size / 1024:.0f} KB")
            if len(produced) != len(sources):
                failures.append("第 1 轮：原图旁输出数量不符")

            # 透明模式必须是 RGBA 且真的有透明像素
            from PIL import Image

            if produced:
                with Image.open(produced[0]) as img:
                    alpha_ok = img.mode == "RGBA" and img.getchannel("A").getextrema()[0] < 250
                print(f"  抽样 {produced[0].name}: mode={img.mode}")
                if not alpha_ok:
                    failures.append(f"第 1 轮：透明模式输出 mode={img.mode} 或不含透明像素")

            window.grab().save(str(OUT_DIR / "04_after_batch.png"))
            print(f"  已保存 {OUT_DIR / '04_after_batch.png'}")

            # 第 2 轮：纯色背景 + 指定文件夹
            window.clear_all()
            window.settings_panel.bg_color.setChecked(True)
            window.settings_panel.set_custom_dir(SMOKE_OUT)
            window.add_inputs([SMOKE_IN])
            print(f"—— 第 2 轮：纯色背景，保存到指定文件夹（{SMOKE_OUT}）")
            window.start()
            return True

        produced = sorted(SMOKE_OUT.glob("*.png"))
        print(f"  输出 {len(produced)} / 期望 {len(sources)}")
        for path in produced:
            print(f"    {path.name}  {path.stat().st_size / 1024:.0f} KB")
        if len(produced) != len(sources):
            failures.append("第 2 轮：指定目录输出数量不符")

        # 纯色背景应当是 RGB（无 alpha）
        from PIL import Image

        if produced:
            with Image.open(produced[0]) as img:
                print(f"  抽样 {produced[0].name}: mode={img.mode} size={img.size}")
                if img.mode != "RGB":
                    failures.append(f"第 2 轮：纯色背景输出 mode={img.mode}，期望 RGB")

        statuses = [(t.src.name, t.status.value, t.elapsed_ms) for t in window._tasks]
        print("  任务状态：")
        for name, status, ms in statuses:
            print(f"    {name}: {status} ({ms}ms)")

        window.grab().save(str(OUT_DIR / "06_after_color.png"))
        print(f"  已保存 {OUT_DIR / '06_after_color.png'}")
        return True

    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(lambda: (print("超时：批处理未在 120 秒内结束"), app.exit(2)))
    deadline.start(120_000)

    def poll() -> None:
        if check(state["round"]):
            state["round"] += 1
            if state["round"] > 2:
                deadline.stop()
                if failures:
                    for item in failures:
                        print(f"失败：{item}")
                    app.exit(1)
                else:
                    print("两轮均通过")
                    app.exit(0)
                return
        QTimer.singleShot(400, poll)

    QTimer.singleShot(600, begin)
    QTimer.singleShot(2000, poll)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
