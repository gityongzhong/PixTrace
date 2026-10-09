"""模型文件的定位与校验。

模型按以下顺序查找：
1. 环境变量 PIXTRACE_MODEL_DIR 指定的目录（最高优先级，便于完全离线/自定义部署）
2. 打包资源目录 models/（PyInstaller 随包附带的极速档在 _internal/models/）
3. 应用目录 models/（便携版解压后把模型放 exe 旁边也能被找到）
4. 用户缓存目录 %LOCALAPPDATA%/pixtrace/models（下载器与手动导入的落点）

第 2、3 项优先于第 4 项：随包附带的权重是经过校验的已知良好文件，
用户缓存里若存在同名损坏文件，不应该反过来把好文件盖掉。

找到后校验 sha256，不匹配则报错，避免"文件下了一半"这类问题被静默吞掉。
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .paths import app_dir, models_cache_dir, resource_dir

_HASH_CHUNK = 1 << 20


def project_root() -> Path:
    """应用目录（冻结后为 exe 所在目录）。保留旧名以免调用方大改。"""
    return app_dir()


def user_cache_dir() -> Path:
    return models_cache_dir()


def search_dirs() -> list[Path]:
    dirs: list[Path] = []
    env = os.environ.get("PIXTRACE_MODEL_DIR")
    if env:
        dirs.append(Path(env).expanduser())
    dirs.append(resource_dir() / "models")
    dirs.append(app_dir() / "models")
    dirs.append(user_cache_dir())
    return dirs


def find_model(filename: str) -> Path | None:
    for directory in search_dirs():
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None


def sha256_of(path: Path, chunk_size: int = _HASH_CHUNK) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    actual = sha256_of(path)
    if actual.lower() != expected.lower():
        raise RuntimeError(
            f"模型文件校验失败：{path.name}\n"
            f"  期望 sha256: {expected}\n"
            f"  实际 sha256: {actual}\n"
            "文件可能损坏或下载不完整，请删除后重新获取。"
        )


def locate(filename: str, expected_sha256: str | None = None, verify_hash: bool = True) -> Path:
    """定位模型文件，可选校验哈希。

    哈希校验对 176MB 的高精档大约耗时 0.3-0.8 秒，批处理作业只需做一次。
    """
    path = find_model(filename)
    if path is None:
        searched = "\n".join(f"  - {d}" for d in search_dirs())
        raise FileNotFoundError(
            f"找不到模型文件 {filename}，已查找以下目录：\n{searched}\n"
            "请把 .onnx 文件放入 models/ 目录，或设置环境变量 PIXTRACE_MODEL_DIR 指向模型所在目录。"
        )
    if verify_hash and expected_sha256:
        verify(path, expected_sha256)
    return path


class ModelState:
    """模型文件状态，供界面显示与下载按钮启用判断。"""

    READY = "ready"
    MISSING = "missing"
    CORRUPT = "corrupt"


def inspect(filename: str, expected_sha256: str | None = None) -> tuple[str, Path | None, str | None]:
    """返回 (状态, 文件路径, 说明)。

    校验失败单独成一类（CORRUPT）而不是和 MISSING 合并：界面上这两者的
    处理方式不同——缺失是「下载」，损坏是「重新下载（覆盖）」，把损坏当缺失
    会让用户点下载却发现没反应。
    """
    path = find_model(filename)
    if path is None:
        return ModelState.MISSING, None, None
    if not expected_sha256:
        return ModelState.READY, path, None

    actual = sha256_of(path)
    if actual.lower() != expected_sha256.lower():
        return (
            ModelState.CORRUPT,
            path,
            f"sha256 不匹配\n  期望 {expected_sha256[:16]}…\n  实际 {actual[:16]}…",
        )
    return ModelState.READY, path, None
