"""界面截图：渲染 GUI 并保存 PNG，用于无人值守的界面自检。

用法：
    python scripts/shot_gui.py          全部场景
    python scripts/shot_gui.py empty    仅空状态

尺寸默认取主窗口的开窗尺寸；要验别的尺寸设环境变量，
例如 `PIXTRACE_SHOT_SIZE=1080x720`。文件名带尺寸后缀，便于逐尺寸对比。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / ".shots"

WALLPAPERS = [
    Path("C:/Windows/Web/Wallpaper/ThemeA/img20.jpg"),
    Path("C:/Windows/Web/Wallpaper/ThemeA/img21.jpg"),
    Path("C:/Windows/Web/Wallpaper/ThemeB/img24.jpg"),
    Path("C:/Windows/Web/Wallpaper/ThemeB/img25.jpg"),
    Path("C:/Windows/Web/Wallpaper/ThemeC/img28.jpg"),
]


def main() -> int:
    from PySide6.QtCore import QEventLoop, QSettings, QTimer
    from PySide6.QtWidgets import QApplication

    from app.ui import style
    from app.ui.main_window import MainWindow
    from app.ui.preview import PreviewWindow

    # 截图要展示默认状态：清掉历史运行留下的参数记忆（含窗口几何，
    # 否则上次关窗的尺寸会盖掉本次要验的开窗尺寸）
    store = QSettings("pixtrace", "pixtrace")
    store.remove("panel/state_json")
    store.remove("panel/state")
    store.remove("window/geometry")
    store.remove("window/geometry2")
    store.sync()

    OUT_DIR.mkdir(exist_ok=True)
    scene = sys.argv[1] if len(sys.argv) > 1 else "all"

    app = QApplication(sys.argv)
    style.apply(app)

    window = MainWindow()
    override = os.environ.get("PIXTRACE_SHOT_SIZE", "").strip().lower()
    if override:
        try:
            width, height = (int(part) for part in override.replace("*", "x").split("x"))
            window.resize(width, height)
        except ValueError:
            print(f"忽略无法解析的 PIXTRACE_SHOT_SIZE={override!r}")
    window.show()
    app.processEvents()
    size_tag = f"_{window.width()}x{window.height()}"

    def settle(ms: int = 320) -> None:
        """等过渡动画跑完再截图。

        只调 processEvents() 是推进一帧就返回，150~200ms 的淡入 / 数值滚动会
        截到中间态：状态文字半透明、进度条还没滚到位置。
        """
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def save(widget, name: str) -> None:
        settle()
        app.processEvents()
        path = OUT_DIR / f"{name}{size_tag}.png"
        widget.grab().save(str(path))
        print(f"已保存 {path}")

    steps: list = []

    if scene in ("all", "empty"):
        steps.append(lambda: save(window, "01_empty"))

    if scene in ("all", "hover"):
        def hover() -> None:
            # 拖拽悬停态：验证自绘的过渡表面（边框 + 底色 + 顶部高光）画对了没有
            window._set_drop_highlight(True)
            save(window, "06_drop_hover")
            window._set_drop_highlight(False)

        steps.append(hover)

    if scene in ("all", "loaded"):
        def loaded() -> None:
            existing = [p for p in WALLPAPERS if p.exists()]
            window.add_inputs(existing)
            window.progress.setRange(0, len(existing))
            window.progress.setValue(max(0, len(existing) - 2))
            window._set_status("3/5 · 平均 1.15s/张 · 剩余约 2 秒")
            # 选中一行，让截图带上选中态（左侧强调条 + 柔和蓝底）
            if window.tree.topLevelItemCount() > 1:
                window.tree.setCurrentItem(window.tree.topLevelItem(1))
            save(window, "02_loaded")

        steps.append(loaded)

    if scene in ("all", "color"):
        def color_mode() -> None:
            window.settings_panel.bg_color.setChecked(True)
            save(window, "05_color_bg")

        steps.append(color_mode)

    if scene in ("all", "preview"):
        def preview() -> None:
            src = next((p for p in WALLPAPERS if p.exists()), None)
            if src is None:
                return
            dialog = PreviewWindow(src, None, window)
            dialog.resize(980, 700)
            dialog.show()

            def capture() -> None:
                save(dialog, "03_preview")
                dialog.close()

            QTimer.singleShot(300, capture)

        steps.append(preview)

    def run_next() -> None:
        if not steps:
            app.quit()
            return
        action = steps.pop(0)
        action()
        QTimer.singleShot(450, run_next)

    QTimer.singleShot(500, run_next)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
