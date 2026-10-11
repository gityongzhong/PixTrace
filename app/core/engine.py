"""推理引擎：封装 onnxruntime session 与完整的 预处理 -> 推理 -> 后处理 管线。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .models import ModelSpec
from .postprocess import normalize_mask, to_mask_image, unletterbox
from .preprocess import letterbox, to_tensor


class InferenceEngine:
    """一个进程一个实例；批量场景下 session 在进程内复用，不重复加载模型。"""

    def __init__(
        self,
        spec: ModelSpec,
        model_path: Path,
        providers: list[str] | None = None,
        intra_op_threads: int | None = 1,
    ) -> None:
        # 延迟导入：让「只是想用 planner/compositor」的调用方不必装 onnxruntime
        import onnxruntime as ort

        self.spec = spec

        options = ort.SessionOptions()
        if intra_op_threads and intra_op_threads > 0:
            options.intra_op_num_threads = intra_op_threads
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.log_severity_level = 3  # 只报错误

        self._session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=providers
        )
        self._input_name = self._session.get_inputs()[0].name
        # 只请求主输出，onnxruntime 会自动裁掉其余输出分支的计算
        self._output_name = self._session.get_outputs()[spec.output_index].name

    def predict_mask(self, rgb: Image.Image, feather: float = 0.0) -> Image.Image:
        """输入 RGB 图，返回同尺寸的 L 模式 alpha 遮罩。"""
        canvas, meta = letterbox(rgb, self.spec.input_size)
        tensor = to_tensor(canvas, self.spec.mean, self.spec.std, self.spec.divide)

        raw = self._session.run([self._output_name], {self._input_name: tensor})[0]
        pred = np.squeeze(raw)
        if pred.ndim != 2:
            raise RuntimeError(f"模型输出形状异常：{raw.shape}，期望 (1,1,H,W)")

        alpha = normalize_mask(pred)
        alpha = unletterbox(alpha, meta)
        return to_mask_image(alpha, feather=feather)
