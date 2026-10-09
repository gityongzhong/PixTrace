"""后处理：把模型输出的遮罩还原到原图尺寸。"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from .preprocess import LetterboxMeta


def normalize_mask(pred: np.ndarray) -> np.ndarray:
    """把值域不确定的原始输出线性拉伸到 [0, 1]。

    模型各输出头的量纲不统一，做一次 min-max 拉伸比假设固定阈值稳健得多。
    """
    pred = np.asarray(pred, dtype=np.float32)
    low = float(pred.min())
    high = float(pred.max())
    if high - low < 1e-8:
        # 全图同值（例如纯色图）时无法判断前景，按全透明处理
        return np.zeros_like(pred, dtype=np.float32)
    return (pred - low) / (high - low)


def unletterbox(mask: np.ndarray, meta: LetterboxMeta) -> np.ndarray:
    """裁掉补边，再缩回原图尺寸，返回 (H, W) float32 in [0, 1]。"""
    content_w, content_h = meta.content_size
    cropped = mask[meta.pad_y : meta.pad_y + content_h, meta.pad_x : meta.pad_x + content_w]

    img = Image.fromarray((np.clip(cropped, 0.0, 1.0) * 255).astype(np.uint8), mode="L")
    img = img.resize(meta.src_size, Image.BILINEAR)
    return np.asarray(img, dtype=np.float32) / 255.0


def to_mask_image(alpha: np.ndarray, feather: float = 0.0) -> Image.Image:
    """转成 L 模式遮罩图，可选高斯羽化。

    羽化是不引入 alpha matting 依赖的前提下，缓解发丝边缘发虚的折中手段：
    半径过大反而会吃掉细节，所以默认关闭，由调用方按素材决定。
    """
    img = Image.fromarray((np.clip(alpha, 0.0, 1.0) * 255).astype(np.uint8), mode="L")
    if feather > 0:
        img = img.filter(ImageFilter.GaussianBlur(feather))
    return img


def mask_coverage(alpha: np.ndarray, threshold: float = 0.5) -> float:
    """前景像素占比，用于识别"几乎没有主体"或"整张都判成主体"的异常结果。"""
    return float((alpha > threshold).mean())
