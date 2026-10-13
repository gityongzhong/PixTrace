"""生成 GitHub 图标资源：assets/github.png（白色剪影 + 透明底）。

为什么是「白色剪影 PNG」而不是直接画彩色图标：
- 界面右下角那个图标要跟主题走——常态灰、悬停提亮、按下取强调色。
  存一张纯白剪影，运行时用 CompositionMode_SourceIn 染上任一颜色即可，
  比存多张彩色图省事，也比把 QtSvg 塞回运行时划算（spec 里 Qt SVG 已剔除）。
- 形状用 GitHub 官方 Octicon 的 mark 路径（16×16 网格，MIT 许可），
  不在代码里手搓贝塞尔——手抄路径出错就是把图标画歪，肉眼很难发现。

渲染在 8 倍尺寸（128×128）上做，缩到 16~20px 显示时边缘才干净。

用法：
    python scripts/make_git_icon.py
输出：
    assets/github.png    128×128 白色剪影，alpha 通道即形状
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "github.png"

# GitHub Octicon "mark-github" 16×16 路径（Octicons, MIT License）
MARK_PATH = (
    "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 "
    "0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13"
    "-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66"
    ".07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15"
    "-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 "
    "2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 "
    "0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21"
    ".15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"
)

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">'
    f'<path fill="#ffffff" d="{MARK_PATH}"/></svg>'
)

SIZE = 128  # 8 倍于 16 的原始网格


def main() -> int:
    # 离屏渲染：不需要真窗口，也不要弹窗
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])

    image = QImage(SIZE, SIZE, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer = QSvgRenderer(QByteArray(SVG.encode("utf-8")))
    if not renderer.isValid():
        print("SVG 解析失败（路径数据有问题）", file=sys.stderr)
        return 1
    renderer.render(painter)
    painter.end()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(OUT)):
        print(f"写入失败：{OUT}", file=sys.stderr)
        return 1
    print(f"已生成 {OUT}  ({image.width()}×{image.height()})")
    del app
    return 0


if __name__ == "__main__":
    sys.exit(main())
