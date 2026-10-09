"""背景合成。

输入永远是「原图 RGB + alpha 遮罩」组成的 RGBA 前景，输出按目标格式决定
是 RGBA（透明 PNG/WebP）还是 RGB（JPEG，或指定了不透明背景）。

合成公式（逐通道）：
    out = fg * a + bg * (1 - a)
由 PIL 的 alpha_composite 完成，它会正确处理预乘与非预乘的转换。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from .types import BackgroundKind, BackgroundSpec, OutputFormat

# 复用已加载的背景图，避免批量处理时每张图都重新读盘
_IMAGE_CACHE: dict[Path, Image.Image] = {}

# 去色染（defringe）的启用门槛：透明区像素的逐通道标准差上限。
# 实测：证件照蓝底 std≈7.5、均匀深色背景 ≈14.4、复杂霓虹背景 ≈44。
# 背景均匀时，边缘半透明像素可用 I = a·fg + (1-a)·bg 反解出"纯前景色"，
# 消除换底色后残留在发丝边缘的原背景色（如蓝底证件照换红底后的蓝边）。
DEFRINGE_STD_MAX = 18.0
DEFRINGE_MAX_SAMPLES = 200_000


def _defringe(rgba: np.ndarray) -> np.ndarray:
    """对半透明边缘像素做去色染，返回新的 RGBA 数组。

    只在背景足够均匀时启用：复杂背景下"背景色"没有单一取值，
    全局中位数没有意义，此时保持原样（观察值本来就是真实混合）。
    """
    alpha = rgba[..., 3]
    bg_mask = alpha < 10
    if bg_mask.mean() < 0.005:  # 几乎没有透明区，无从估计背景色
        return rgba

    rgb = rgba[..., :3].astype(np.float32)
    samples = rgb[bg_mask]
    if samples.shape[0] > DEFRINGE_MAX_SAMPLES:
        rng = np.random.default_rng(0)  # 固定种子：同一输入永远得到同一输出
        idx = rng.choice(samples.shape[0], DEFRINGE_MAX_SAMPLES, replace=False)
        samples = samples[idx]
    if samples.std(axis=0).max() > DEFRINGE_STD_MAX:
        return rgba
    bg_color = np.median(samples, axis=0)

    soft = (alpha > 0) & (alpha < 255)
    if not soft.any():
        return rgba

    sa = rgba[..., 3:4][soft].astype(np.float32) / 255.0
    unmixed = (rgb[soft] - (1.0 - sa) * bg_color) / np.clip(sa, 1e-3, None)
    rgb[soft] = np.clip(unmixed, 0, 255)

    out = rgba.copy()
    out[..., :3] = rgb.astype(np.uint8)
    return out


def build_foreground(rgb: Image.Image, mask: Image.Image) -> Image.Image:
    """把单通道遮罩挂到原图 alpha 通道上，得到 RGBA 前景（含去色染）。"""
    fg = rgb.convert("RGB")
    if mask.size != fg.size:
        mask = mask.resize(fg.size, Image.BILINEAR)
    rgba = fg.convert("RGBA")
    rgba.putalpha(mask.convert("L"))

    arr = np.asarray(rgba).copy()
    return Image.fromarray(_defringe(arr), "RGBA")


def _cover_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """等比缩放到恰好覆盖目标尺寸，居中裁剪多余部分。"""
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(target_w, math.ceil(src_w * scale))
    new_h = max(target_h, math.ceil(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _load_background_image(path: Path) -> Image.Image:
    cached = _IMAGE_CACHE.get(path)
    if cached is None:
        cached = Image.open(path).convert("RGB")
        _IMAGE_CACHE[path] = cached
    return cached


def _make_background(
    spec: BackgroundSpec,
    size: tuple[int, int],
    source_rgb: Image.Image,
) -> Image.Image | None:
    """生成填充层。返回 None 表示保持透明。"""
    if spec.kind is BackgroundKind.TRANSPARENT:
        return None

    if spec.kind is BackgroundKind.COLOR:
        return Image.new("RGB", size, spec.color)

    if spec.kind is BackgroundKind.IMAGE:
        assert spec.image_path is not None
        return _cover_resize(_load_background_image(spec.image_path), size)

    if spec.kind is BackgroundKind.BLURRED:
        bg = source_rgb.convert("RGB")
        # 半径按图片短边缩放，保证不同分辨率下观感一致
        radius = max(1.0, spec.blur_radius * min(size) / 1000.0)
        bg = bg.filter(ImageFilter.GaussianBlur(radius))
        if spec.darken > 0:
            factor = 1.0 - spec.darken
            bg = bg.point(lambda v: int(v * factor))
        return bg

    raise ValueError(f"未知的背景类型：{spec.kind}")


def compose(
    foreground: Image.Image,
    spec: BackgroundSpec,
    source_rgb: Image.Image,
    output_format: OutputFormat,
) -> Image.Image:
    """把 RGBA 前景与背景合成为最终图像。"""
    size = foreground.size

    # JPEG 不支持 alpha：即使调用方要求透明，也必须给一个不透明的兜底底色
    if output_format is OutputFormat.JPEG and spec.kind is BackgroundKind.TRANSPARENT:
        spec = BackgroundSpec(kind=BackgroundKind.COLOR, color=(255, 255, 255))

    bg = _make_background(spec, size, source_rgb)

    if bg is None:
        return foreground

    merged = Image.alpha_composite(bg.convert("RGBA"), foreground)
    if bg.mode == "RGB":
        return merged.convert("RGB")
    return merged


def clear_cache() -> None:
    _IMAGE_CACHE.clear()
