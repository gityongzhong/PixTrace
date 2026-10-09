"""扫描输入、规划任务列表。

规划阶段就把 src 与 dst 全部确定下来，好处：
- 可以在开始前做冲突检测与预检
- 失败重跑时不需要重新推导路径

输出落点有三种：
1. alongside=True（界面默认）：与原图放在同一文件夹，文件名加 `-无背景` 后缀
2. output_dir 指定目录：可选保留子目录结构，同样加后缀
3. 两者都没有：回落到源文件旁的 _PixTrace 子目录（CLI 的历史默认行为）

凡是可能写进「原图所在目录」的产物都带后缀，扫描时也会跳过带后缀的文件——
否则第二次运行会把自己的输出当成新素材，抠出 `xxx-无背景-无背景.png`。
`_PixTrace` 子目录同样在扫描时跳过。
"""

from __future__ import annotations

from pathlib import Path

from ..core.types import JobOptions, Task

SUPPORTED_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
)

# 默认输出目录名：源文件旁的同级子目录（仅在未指定落点且非 alongside 时使用）
AUTO_OUTPUT_DIRNAME = "_PixTrace"

# 输出文件名后缀：写在原图旁边时必须加，避免覆盖原图、也避免被再次扫描
OUTPUT_NAME_SUFFIX = "-无背景"


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_SUFFIXES


def is_generated(path: Path) -> bool:
    """判断是否是本工具自己的产物（带 -无背景 后缀）。"""
    return path.stem.endswith(OUTPUT_NAME_SUFFIX)


def _iter_images(root: Path, exclude: set[Path]) -> list[Path]:
    """递归收集图片，跳过 exclude 中的目录、_PixTrace 目录与已生成的产物。"""
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if is_generated(path):
            continue
        if any(parent in exclude for parent in path.parents):
            continue
        if any(part == AUTO_OUTPUT_DIRNAME for part in path.parts):
            continue
        found.append(path)
    return sorted(found)


def _dedupe(dst: Path, used: set[str]) -> Path:
    """多输入映射到同一输出目录时避免互相覆盖。"""
    key = str(dst).lower()
    if key not in used:
        used.add(key)
        return dst

    index = 1
    while True:
        candidate = dst.with_name(f"{dst.stem}_{index}{dst.suffix}")
        candidate_key = str(candidate).lower()
        if candidate_key not in used:
            used.add(candidate_key)
            return candidate
        index += 1


def _resolve_dst(
    src: Path,
    rel: Path,
    auto_out: Path,
    options: JobOptions,
) -> Path:
    suffix = options.output_format.suffix
    marked = src.stem + OUTPUT_NAME_SUFFIX + suffix

    if options.output_dir is not None:
        if options.keep_structure:
            return options.output_dir / rel.parent / marked
        return options.output_dir / marked

    if options.alongside:
        return src.parent / marked

    return auto_out / rel.parent / (src.stem + suffix)


def build_tasks(inputs: list[Path], options: JobOptions) -> list[Task]:
    """把「文件或目录的混合列表」展开成具体任务列表。

    - 文件输入：输出到该文件所在的位置（alongside / 指定目录 / _PixTrace）
    - 目录输入：递归扫描，输出落点按同样规则推导
    - 扫描时自动跳过 _PixTrace 自身、指定的 output_dir 以及本工具的既有产物
    """
    if not inputs:
        raise ValueError("至少需要一个输入路径")

    tasks: list[Task] = []
    used: set[str] = set()

    for raw in inputs:
        entry = raw.expanduser()
        if not entry.exists():
            raise FileNotFoundError(f"输入不存在：{entry}")
        entry = entry.resolve()

        if entry.is_file():
            if not is_supported(entry):
                raise ValueError(f"不支持的图片格式：{entry.suffix}")
            files = [entry]
            base = entry.parent
            auto_out = entry.parent / AUTO_OUTPUT_DIRNAME
            exclude: set[Path] = set()
        else:
            auto_out = entry / AUTO_OUTPUT_DIRNAME
            base = entry
            exclude = {auto_out}
            if options.output_dir is not None:
                resolved = options.output_dir.expanduser()
                try:
                    exclude.add(resolved.resolve())
                except OSError:
                    exclude.add(resolved)
            files = _iter_images(entry, exclude)

        for src in files:
            rel = src.relative_to(base)
            dst = _resolve_dst(src, rel, auto_out, options)
            tasks.append(Task(src=src, rel=rel, dst=_dedupe(dst, used)))

    return tasks


def resolve_workers(model_workers_hint: int, requested: int, cpu_count: int) -> int:
    """决定进程数：用户显式指定优先，否则取模型档位建议值与核数的较小者。"""
    if requested > 0:
        return max(1, requested)
    return max(1, min(model_workers_hint, cpu_count))
