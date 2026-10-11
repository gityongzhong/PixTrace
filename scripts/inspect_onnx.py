"""探测 ONNX 模型的输入输出规格。

接入新模型时先跑这个脚本，用实测结果填 ModelSpec，不要凭记忆写参数。
用法：
    python scripts/inspect_onnx.py models/*.onnx
"""

from __future__ import annotations

import sys
from pathlib import Path

import onnxruntime as ort


def describe(path: Path) -> None:
    size_mb = path.stat().st_size / 1024 / 1024
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

    print(f"=== {path.name}  ({size_mb:.1f} MB) ===")
    for item in session.get_inputs():
        print(f"  input   name={item.name!r}  shape={item.shape}  type={item.type}")
    for index, item in enumerate(session.get_outputs()):
        print(f"  output[{index}] name={item.name!r}  shape={item.shape}  type={item.type}")
    print()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    for arg in sys.argv[1:]:
        describe(Path(arg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
