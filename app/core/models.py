"""模型注册表。

参数全部来自 scripts/inspect_onnx.py 的实测输出，不要凭记忆改动：
  - u2netp.onnx            输入 'input.1'     [1,3,320,320]，7 个输出，主输出取 [0]
  - isnet-general-use.onnx 输入 'input_image' [1,3,1024,1024]，12 个输出，主输出取 [0]

归一化与几何变换的选型依据（scripts/probe_norm.py 对照实验 + rembg 官方源码核对）：
  - u2netp 用 ImageNet 常数 (0.485,0.456,0.406)/(0.229,0.224,0.225)
  - isnet-general-use 用 (0.5,0.5,0.5)/(1.0,1.0,1.0)，与 u2net 家族不同！
    两者预处理常数不一致，必须逐模型核对官方推理脚本，严禁凭家族经验推广
  - div_max 与 div255 在 8bit 输入上等价（像素最大值就是 255），取 div255 更可预测
  - letterbox 优于直接拉伸：宽幅图被强行拉伸时主体几何变形，遮罩出现切边伪影
"""

from __future__ import annotations

from dataclasses import dataclass

from .preprocess import IMAGENET_MEAN, IMAGENET_STD


@dataclass(frozen=True)
class ModelSpec:
    key: str
    display: str
    filename: str
    sha256: str
    input_size: int
    output_index: int = 0
    divide: str = "div255"
    mean: tuple[float, float, float] = IMAGENET_MEAN
    std: tuple[float, float, float] = IMAGENET_STD
    # 高精档模型 176MB，每进程一份内存，建议并发数低于极速档
    workers_hint: int = 4
    # 批量工作进程的 intra_op 线程数；0 表示交给 onnxruntime 默认（用满核）。
    # 实测（12 核）：小模型 u2netp 限制单线程 + 多进程吞吐最高；
    # 大模型 isnet 限制单线程会让单张推理从 1.15s 劣化到 7.2s，
    # 必须保留默认多线程、减少进程数。
    worker_intra: int = 1


MODELS: dict[str, ModelSpec] = {
    "u2netp": ModelSpec(
        key="u2netp",
        display="极速",
        filename="u2netp.onnx",
        sha256="309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8",
        input_size=320,
        workers_hint=6,
    ),
    "isnet-general-use": ModelSpec(
        key="isnet-general-use",
        display="高精",
        filename="isnet-general-use.onnx",
        sha256="60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a",
        input_size=1024,
        # DIS 家族专用常数（来源：rembg dis_general_use.py，与 DIS 官方推理一致）
        mean=(0.5, 0.5, 0.5),
        std=(1.0, 1.0, 1.0),
        workers_hint=1,
        worker_intra=0,
    ),
}

# CLI 友好名 -> 注册表 key
ALIASES: dict[str, str] = {
    "fast": "u2netp",
    "极速": "u2netp",
    "quality": "isnet-general-use",
    "高精": "isnet-general-use",
}

# 界面固定使用高精档：两个功能（去背景 / 换纯色底）都吃边缘质量，
# 实测发丝与复杂边缘比极速档好一档，代价是单张约 1.2 秒。
DEFAULT_MODEL_KEY = "isnet-general-use"


def resolve_model(name: str) -> ModelSpec:
    key = ALIASES.get(name, name)
    spec = MODELS.get(key)
    if spec is None:
        available = ", ".join(f"{k}({v.display})" for k, v in MODELS.items())
        raise KeyError(f"未知模型档位：{name}。可用档位：{available}")
    return spec
