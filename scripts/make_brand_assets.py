"""品牌资产生成：从设计师给的源稿（assets/logo-source.png）派生全部图标。

为什么需要这一步而不是直接把源稿塞进仓库了事：
- 应用图标要的是「圆角方形」的 P 字标，源稿是带文字的完整方形画布；
- Windows .ico 要 16~256 一整串尺寸，且小尺寸必须从高清圆角版缩下来，边缘才干净;
- 标题栏小标、关于页大图、README 各用不同裁剪——派生规则写在这里，源稿一换全部可复现。

圆角半径取 22%（对齐 macOS 图标约 22.4% 的连续曲率观感），先在 4 倍尺寸上做
圆角蒙版再缩小，避免小尺寸图标边缘出现锯齿。

用法：
    python scripts/make_brand_assets.py
输出：
    assets/pixtrace.png    256×256 圆角 P 字标（窗口图标 / README）
    assets/pixtrace.ico    多尺寸 Windows 图标（exe 资源）
    assets/logo-mark.png   128×128 圆角 P 字标（标题栏）
    assets/logo-full.png   圆角完整 logo（关于页）
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SOURCE = ASSETS / "logo-source.png"

ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]
ROUND_RATIO = 0.22  # macOS 图标圆角比例
SS = 4  # 超采样倍数


def rounded(image: Image.Image, ratio: float = ROUND_RATIO) -> Image.Image:
    """按比例圆角化，4 倍超采样抗锯齿。"""
    size = image.size
    big = (size[0] * SS, size[1] * SS)
    mask = Image.new("L", big, 0)
    draw = ImageDraw.Draw(mask)
    radius = int(min(big) * ratio)
    draw.rounded_rectangle([0, 0, big[0] - 1, big[1] - 1], radius=radius, fill=255)
    mask = mask.resize(size, Image.LANCZOS)

    out = image.convert("RGBA")
    out.putalpha(mask)
    return out


def _content_band(gray: Image.Image, threshold: int = 40, gap_rows: int = 12) -> tuple[int, int]:
    """按行亮度找出第一段内容带：从首个亮行开始，遇到连续空行带即结束。

    源稿是「上 P 字标 + 下 PixTrace 文字标」两块内容，中间隔一条黑缝；
    直接对全图找包围盒会把文字标也卷进来，所以先按行分段再取第一段。
    """
    width, height = gray.size
    pixels = gray.load()
    row_max = [max(pixels[x, y] for x in range(0, width, 2)) for y in range(height)]

    start = next((y for y, m in enumerate(row_max) if m > threshold), 0)
    end = start
    gap = 0
    for y in range(start, height):
        if row_max[y] > threshold:
            end = y
            gap = 0
        else:
            gap += 1
            if gap >= gap_rows:
                break
    return start, end + 1


def mark_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    """定位源稿上半部分的 P 字标（含棋盘格）区域，返回正方形裁剪框。"""
    width, height = image.size
    gray = image.convert("L")
    top, bottom = _content_band(gray)
    band = gray.crop((0, top, width, bottom))
    pixels = band.load()
    band_width, band_height = band.size
    col_max = [
        max(pixels[x, y] for y in range(0, band_height, 2)) for x in range(band_width)
    ]
    left = next((x for x, m in enumerate(col_max) if m > 40), 0)
    right = band_width - next(
        (x for x, m in enumerate(reversed(col_max)) if m > 40), 0
    )

    side = max(right - left, bottom - top)
    pad = int(side * 0.06)
    side += pad * 2
    center_x = (left + right) // 2
    center_y = top + (bottom - top) // 2
    x0 = max(0, center_x - side // 2)
    y0 = max(0, center_y - side // 2)
    return (x0, y0, min(width, x0 + side), min(height, y0 + side))


def main() -> int:
    if not SOURCE.is_file():
        print(f"缺少源稿：{SOURCE}")
        print("把设计稿放到该路径后重跑（原始来源见项目交付记录）。")
        return 1

    source = Image.open(SOURCE).convert("RGBA")

    # P 字标方形裁剪 → 圆角 → 各尺寸
    mark = source.crop(mark_bbox(source))
    mark_1024 = mark.resize((1024, 1024), Image.LANCZOS)
    mark_rounded = rounded(mark_1024)

    mark_rounded.resize((256, 256), Image.LANCZOS).save(ASSETS / "pixtrace.png")
    mark_rounded.resize((128, 128), Image.LANCZOS).save(ASSETS / "logo-mark.png")

    icon_images = [
        mark_rounded.resize((size, size), Image.LANCZOS) for size in ICON_SIZES
    ]
    icon_images[-1].save(
        ASSETS / "pixtrace.ico", format="ICO", sizes=[(s, s) for s in ICON_SIZES]
    )

    # 完整 logo（含文字标）圆角版，用于关于页与 README 头图
    full = source.copy()
    full.thumbnail((1024, 1024), Image.LANCZOS)
    rounded(full, ratio=0.10).save(ASSETS / "logo-full.png")

    for name in ("pixtrace.png", "pixtrace.ico", "logo-mark.png", "logo-full.png"):
        target = ASSETS / name
        print(f"已生成 {target}  {target.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
