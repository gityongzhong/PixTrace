"""生成 README 用的界面展示图，输出到 docs/screenshots/。

用法：
    python scripts/shot_readme.py 图片1 [图片2 ...]

说明：
- 素材会先复制到 .shots/readme_demo/（.shots 不入库），处理结果也落在那里，
  不碰原图所在目录；建议选主体清晰、背景干净的图片，抠图对比效果最好。
- 会真实跑一遍高精模型（isnet）批处理，需要 models/ 下有模型文件。
- 建议加 QT_SCALE_FACTOR=2 运行：窗口逻辑尺寸不变（860x560），
  输出像素翻倍（1720x1120），README 里显示更清晰。
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "screenshots"
# 演示目录可用环境变量覆盖：预览窗底部会显示素材的完整路径，
#subst 一个盘符（如 X:）能让截图里的路径干净些
DEMO = Path(os.environ.get("PIXTRACE_SHOT_DEMO", ROOT / ".shots" / "readme_demo"))

POLL_MS = 150
TIMEOUT_MS = 180_000  # 批处理上限；isnet 单张 1-2s，3 张远用不完


def main(argv: list[str]) -> int:
    sources = [Path(p) for p in argv]
    if not sources:
        print("用法: python scripts/shot_readme.py 图片1 [图片2 ...]")
        return 2
    missing = [p for p in sources if not p.is_file()]
    if missing:
        print("素材不存在:", ", ".join(str(p) for p in missing))
        return 2

    DEMO.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    demo_paths: list[Path] = []
    for i, p in enumerate(sources, 1):
        dst = DEMO / f"示例-{i:02d}{p.suffix.lower()}"
        if p.resolve() != dst.resolve():
            shutil.copyfile(p, dst)
        demo_paths.append(dst)

    from PySide6.QtCore import QEventLoop, QSettings, QTimer
    from PySide6.QtWidgets import QApplication

    from app.ui import style
    from app.ui.main_window import MainWindow
    from app.ui.preview import PreviewWindow

    # 展示图必须呈现默认状态：清掉历史运行留下的参数与几何记忆
    store = QSettings("pixtrace", "pixtrace")
    for key in ("panel/state_json", "panel/state", "window/geometry", "window/geometry2"):
        store.remove(key)
    store.sync()

    app = QApplication([])
    style.apply(app)
    window = MainWindow()
    window.show()

    def settle(ms: int = 350) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def grab(widget, name: str) -> None:
        app.processEvents()
        path = OUT / name
        widget.grab().save(str(path))
        print("已保存", path)

    # 1. 空状态（也是默认打开的样子）
    settle(400)
    grab(window, "main.png")

    # 2. 真实批处理：列表的「完成/耗时」是跑出来的，不是摆拍
    window.add_inputs(demo_paths)
    settle(300)
    window.start()
    waited = 0
    while not window.start_button.isEnabled() and waited < TIMEOUT_MS:
        loop = QEventLoop()
        QTimer.singleShot(POLL_MS, loop.quit)
        loop.exec()
        waited += POLL_MS
        app.processEvents()
    if not window.start_button.isEnabled():
        print("批处理超时，退出")
        return 1
    settle(500)
    grab(window, "tasks.png")

    # 3. 对比预览：open_preview 走模态 exec() 会阻塞脚本，这里直接构造同样的窗口
    src = demo_paths[0]
    dst = src.with_name(src.stem + "-无背景.png")
    if not dst.exists():
        print("未找到批处理产物，跳过预览图")
        return 0
    dialog = PreviewWindow(src, dst, window)
    dialog.show()
    settle(800)
    grab(dialog, "preview.png")
    dialog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
