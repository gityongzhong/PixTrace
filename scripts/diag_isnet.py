"""isnet 输出异常诊断：换不同输入归一化，看哪种能让模型产生信号。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def main() -> int:
    sample = sys.argv[1] if len(sys.argv) > 1 else "C:/Users/Administrator/Pictures/我.jpg"
    img = Image.open(sample).convert("RGB").resize((1024, 1024), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32)

    session = ort.InferenceSession(
        str(ROOT / "models" / "isnet-general-use.onnx"), providers=["CPUExecutionProvider"]
    )
    input_name = session.get_inputs()[0].name
    # 只取前 6 个输出（都是 [1,1,1024,1024] 的侧输出/主输出）
    out_names = [o.name for o in session.get_outputs()[:6]]

    variants: dict[str, np.ndarray] = {
        "imagenet(div255)": ((arr / 255.0) - MEAN) / STD,
        "imagenet(div_max)": ((arr / arr.max()) - MEAN) / STD,
        "unit01": arr / 255.0,
        "minus1to1": arr / 127.5 - 1.0,
        "raw0255": arr,
        "bgr_imagenet": ((arr[:, :, ::-1] / 255.0) - MEAN) / STD,
    }

    for label, x in variants.items():
        tensor = np.ascontiguousarray(np.transpose(x, (2, 0, 1))[None], dtype=np.float32)
        outputs = session.run(out_names, {input_name: tensor})
        cells = "  ".join(
            f"[{i}]max={o.max():7.3f} mean={o.mean():7.4f}" for i, o in enumerate(outputs)
        )
        print(f"{label:18s} {cells}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
