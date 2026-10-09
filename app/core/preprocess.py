"""预处理：把任意尺寸的 RGB 图片变成模型需要的 NCHW float32 张量。

采用 letterbox（等比缩放 + 补边）而非直接拉伸。直接拉伸会让极端长宽比的
图片（如 3:1 的横幅）遮罩发生形变；letterbox 的代价是长边方向的有效分辨率
略有下降，但几何关系保持正确，且后处理可以精确反解。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass(frozen=True)
class LetterboxMeta:
    """记录 letterbox 的几何变换，供后处理精确反解。"""

    src_size: tuple[int, int]  # 原图 (w, h)
    dst_size: int  # 模型输入边长
    content_size: tuple[int, int]  # 缩放后实际内容的 (w, h)
    pad_x: int  # 画布内左侧补边宽度
    pad_y: int  # 画布内顶部补边高度


def letterbox(img: Image.Image, size: int, fill: int = 0) -> tuple[np.ndarray, LetterboxMeta]:
    """等比缩放并居中贴到 size×size 画布上。"""
    rgb = img.convert("RGB")
    src_w, src_h = rgb.size
    scale = size / max(src_w, src_h)

    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    resized = rgb.resize((new_w, new_h), Image.BILINEAR)

    canvas = Image.new("RGB", (size, size), (fill, fill, fill))
    pad_x = (size - new_w) // 2
    pad_y = (size - new_h) // 2
    canvas.paste(resized, (pad_x, pad_y))

    meta = LetterboxMeta(
        src_size=(src_w, src_h),
        dst_size=size,
        content_size=(new_w, new_h),
        pad_x=pad_x,
        pad_y=pad_y,
    )
    return np.asarray(canvas), meta


def to_tensor(
    canvas: np.ndarray,
    mean: tuple[float, float, float] = IMAGENET_MEAN,
    std: tuple[float, float, float] = IMAGENET_STD,
    divide: str = "max",
) -> np.ndarray:
    """HWC uint8 -> NCHW float32。

    divide 控制前置缩放方式，两个模型族都沿用各自官方推理脚本的做法：
      "max"    除以像素最大值（U^2-Net / DIS 官方实现）
      "div255" 除以 255（常规做法）
    """
    arr = canvas.astype(np.float32)

    if divide == "max":
        peak = float(arr.max())
        if peak > 0:
            arr /= peak
    elif divide == "div255":
        arr /= 255.0
    else:
        raise ValueError(f"未知的归一化方式：{divide}")

    mean_arr = np.asarray(mean, dtype=np.float32)
    std_arr = np.asarray(std, dtype=np.float32)
    arr = (arr - mean_arr) / std_arr

    return np.ascontiguousarray(np.transpose(arr, (2, 0, 1))[None, ...], dtype=np.float32)
