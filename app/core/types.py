"""统一的数据类型：贯穿 core / batch / cli。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class OutputFormat(str, Enum):
    """输出编码格式。JPEG 不带 alpha，必须配合非透明背景。"""

    PNG = "png"
    WEBP = "webp"
    JPEG = "jpg"

    @property
    def suffix(self) -> str:
        return {"png": ".png", "webp": ".webp", "jpg": ".jpg"}[self.value]

    @property
    def supports_alpha(self) -> bool:
        return self is not OutputFormat.JPEG


class BackgroundKind(str, Enum):
    TRANSPARENT = "transparent"
    COLOR = "color"
    IMAGE = "image"
    BLURRED = "blurred"


@dataclass(frozen=True)
class BackgroundSpec:
    """背景合成参数。

    kind=COLOR    用 color 填底
    kind=IMAGE    用 image_path 按 cover 方式缩放后铺满
    kind=BLURRED  用原图自身高斯模糊后铺底，可轻微压暗以突出主体
    """

    kind: BackgroundKind = BackgroundKind.TRANSPARENT
    color: tuple[int, int, int] = (255, 255, 255)
    image_path: Path | None = None
    blur_radius: float = 30.0
    darken: float = 0.0

    def __post_init__(self) -> None:
        if self.kind is BackgroundKind.IMAGE and self.image_path is None:
            raise ValueError("BackgroundKind.IMAGE 必须提供 image_path")
        if not 0.0 <= self.darken <= 1.0:
            raise ValueError("darken 必须落在 [0, 1]")


@dataclass
class JobOptions:
    """一次批处理作业的完整参数。

    界面只暴露「背景」与「保存位置」两项，其余字段是固定策略（GUI 里写死），
    保留成参数是为了 CLI 与自检脚本仍能精确控制，也便于将来扩展。
    """

    # 默认高精档：发丝与复杂边缘明显更好，实测单张约 1.2 秒
    model_key: str = "isnet-general-use"
    output_format: OutputFormat = OutputFormat.PNG
    background: BackgroundSpec = field(default_factory=BackgroundSpec)

    # None 表示不指定目录，此时由 alongside 决定落点
    output_dir: Path | None = None
    keep_structure: bool = True
    # True：输出到原图所在文件夹（文件名加 -无背景 后缀，不覆盖原图）
    # False 且 output_dir=None：输出到源文件旁的 _PixTrace 子目录（CLI 历史默认）
    alongside: bool = False

    # 0 表示按模型档位与 CPU 核数自动决定
    workers: int = 0
    # 遮罩边缘羽化半径（像素），0 表示不羽化
    feather: float = 0.0
    overwrite: bool = False
    jpeg_quality: int = 92


class TaskStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Task:
    """单个待处理文件。dst 在扫描阶段就确定，便于预检与断点重跑。"""

    src: Path
    rel: Path
    dst: Path
    status: TaskStatus = TaskStatus.PENDING
    error: str = ""
    elapsed_ms: int = 0


@dataclass
class JobReport:
    """作业结束后的汇总，供 CLI 打印与失败重跑使用。"""

    total: int = 0
    done: int = 0
    failed: int = 0
    skipped: int = 0
    elapsed_ms: int = 0
    failures: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def avg_ms(self) -> float:
        return self.elapsed_ms / self.done if self.done else 0.0
