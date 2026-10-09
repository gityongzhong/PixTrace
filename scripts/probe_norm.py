"""预处理参数对照实验。

要确定两件事：
  1. 归一化方式：除以像素最大值（U^2-Net/DIS 官方实现）还是除以 255
  2. 几何变换：直接拉伸（训练时的分布）还是 letterbox（保持长宽比）

判据不是"看起来差不多"，而是遮罩的分布形态：一个可信的 alpha 遮罩应该是
双峰的（大面积接近 0 或接近 1，中间过渡带很窄），且前景占比不应贴近 0% 或 100%。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.models import MODELS  # noqa: E402
from app.core.postprocess import normalize_mask  # noqa: E402
from app.core.preprocess import to_tensor  # noqa: E402

OUT_DIR = ROOT / ".probe"


@dataclass(frozen=True)
class Geometry:
    mode: str
    src_size: tuple[int, int]
    content_size: tuple[int, int]
    pad: tuple[int, int]


def prepare(img: Image.Image, size: int, mode: str) -> tuple[np.ndarray, Geometry]:
    rgb = img.convert("RGB")
    src_w, src_h = rgb.size

    if mode == "stretch":
        resized = rgb.resize((size, size), Image.BILINEAR)
        geo = Geometry(mode, (src_w, src_h), (size, size), (0, 0))
        return np.asarray(resized), geo

    if mode == "letterbox":
        scale = size / max(src_w, src_h)
        new_w = max(1, round(src_w * scale))
        new_h = max(1, round(src_h * scale))
        resized = rgb.resize((new_w, new_h), Image.BILINEAR)
        canvas = Image.new("RGB", (size, size), (0, 0, 0))
        pad_x = (size - new_w) // 2
        pad_y = (size - new_h) // 2
        canvas.paste(resized, (pad_x, pad_y))
        geo = Geometry(mode, (src_w, src_h), (new_w, new_h), (pad_x, pad_y))
        return np.asarray(canvas), geo

    raise ValueError(mode)


def restore(alpha: np.ndarray, geo: Geometry) -> np.ndarray:
    if geo.mode == "stretch":
        img = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8), "L")
        return np.asarray(img.resize(geo.src_size, Image.BILINEAR), dtype=np.float32) / 255.0

    pad_x, pad_y = geo.pad
    content_w, content_h = geo.content_size
    cropped = alpha[pad_y : pad_y + content_h, pad_x : pad_x + content_w]
    img = Image.fromarray((np.clip(cropped, 0, 1) * 255).astype(np.uint8), "L")
    return np.asarray(img.resize(geo.src_size, Image.BILINEAR), dtype=np.float32) / 255.0


def predict(session, img, size, divide, mode, mean, std, out_index=0) -> np.ndarray:
    canvas, geo = prepare(img, size, mode)
    tensor = to_tensor(canvas, mean, std, divide)
    feeds = {session.get_inputs()[0].name: tensor}
    pred = session.run([session.get_outputs()[out_index].name], feeds)[0]
    return restore(normalize_mask(np.squeeze(pred)), geo)


def stats(alpha: np.ndarray) -> str:
    low = float((alpha < 0.1).mean()) * 100
    high = float((alpha > 0.9).mean()) * 100
    mid = 100 - low - high
    return (
        f"mean={alpha.mean():.3f}  fg(>0.5)={float((alpha > 0.5).mean()) * 100:5.1f}%  "
        f"低端={low:5.1f}% 过渡={mid:5.1f}% 高端={high:5.1f}%"
    )


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)

    cases = [
        ("u2netp", ROOT / "models" / "u2netp.onnx", "u2netp"),
        ("isnet", ROOT / "models" / "isnet-general-use.onnx", "isnet-general-use"),
    ]

    samples = [
        ("人像", Path("C:/Users/Administrator/Pictures/我.jpg")),
        ("壁纸", Path("C:/Windows/Web/Wallpaper/ThemeA/img20.jpg")),
    ]

    combos = [
        ("div_max+stretch", "max", "stretch"),
        ("div_max+letterbox", "max", "letterbox"),
        ("div255+stretch", "div255", "stretch"),
        ("div255+letterbox", "div255", "letterbox"),
    ]

    for model_key, model_path, spec_key in cases:
        spec = MODELS[spec_key]
        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        for sample_name, sample_path in samples:
            if not sample_path.exists():
                print(f"[跳过] 素材不存在：{sample_path}")
                continue

            with Image.open(sample_path) as raw:
                img = raw.convert("RGB")

            print(f"\n### {model_key} / {sample_name}  ({img.size[0]}x{img.size[1]})")
            tiles: list[Image.Image] = []
            for label, divide, mode in combos:
                alpha = predict(session, img, spec.input_size, divide, mode, spec.mean, spec.std)
                print(f"  {label:22s} {stats(alpha)}")

                tile = Image.fromarray((alpha * 255).astype(np.uint8), "L").resize((360, 360))
                tiles.append(tile)

                Image.fromarray((alpha * 255).astype(np.uint8), "L").save(
                    OUT_DIR / f"{model_key}_{sample_name}_{label.replace('+', '_')}.png"
                )

            sheet = Image.new("L", (360 * len(tiles), 360), 0)
            for index, tile in enumerate(tiles):
                sheet.paste(tile, (index * 360, 0))
            sheet.save(OUT_DIR / f"sheet_{model_key}_{sample_name}.png")

    print(f"\n结果已写入 {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
