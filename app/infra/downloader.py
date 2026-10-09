"""模型文件下载：断点续传 + sha256 校验 + 失败重试。

刻意只用标准库 urllib，不引入 requests：发行包每多一个依赖就多一份体积与
许可审查负担，而这里需要的功能（Range 续传、跟随重定向、超时、流式读取）
urllib 全都有。

下载落点固定在**用户数据目录**（%LOCALAPPDATA%/pixtrace/models），不写应用目录：
安装到 Program Files 时应用目录不可写，而且 UAC 虚拟化会把文件悄悄重定向到
VirtualStore，造成"下了但找不到"这类极难排查的问题。

失败重试语义：网络错误与哈希校验失败都算一次失败，保持 .part 文件以便续传；
只有校验失败会主动删除 .part（内容已确定是坏的，续下去没有意义）。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .model_store import sha256_of

USER_AGENT = "pixtrace-model-downloader/1.0 (+https://github.com/)"
CHUNK = 1 << 18  # 256 KiB
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3
RETRY_BACKOFF = 2.0
PROGRESS_INTERVAL = 0.15  # 秒，避免进度回调把 UI 事件循环刷爆

# 默认下载源。models 为 Apache-2.0（U^2-Net / DIS 官方权重），此处指向
# 已完成 ONNX 转换且哈希可核对的发布包。
#
# 维护者发布自己的 Release 后，应把下面的地址替换为自有仓库地址，
# 见 README「模型分发」一节。
DEFAULT_SOURCES: dict[str, list[str]] = {
    "u2netp.onnx": [
        "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx",
    ],
    "isnet-general-use.onnx": [
        "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx",
    ],
}

SOURCES_FILENAME = "sources.json"
MIRROR_ENV = "PIXTRACE_MIRROR_PREFIX"


class DownloadCancelled(Exception):
    """用户主动取消，不算错误。"""


class DownloadError(RuntimeError):
    """下载或校验失败（已耗尽重试）。"""


@dataclass(frozen=True)
class Progress:
    downloaded: int
    total: int  # -1 表示服务端未提供长度
    speed_bps: float
    resumed_from: int = 0

    @property
    def fraction(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(1.0, self.downloaded / self.total)

    @property
    def eta_s(self) -> float | None:
        if self.total <= 0 or self.speed_bps <= 0:
            return None
        remaining = self.total - self.downloaded
        if remaining <= 0:
            return 0.0
        return remaining / self.speed_bps


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    bytes_written: int
    resumed_from: int
    elapsed_s: float
    url: str


# --------------------------------------------------------------- 下载源配置
def _load_source_config() -> dict:
    config_path = paths.user_data_dir() / SOURCES_FILENAME
    if not config_path.is_file():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def sources_for(filename: str) -> list[str]:
    """该模型文件的候选下载地址，按优先级排列。

    镜像前缀（sources.json 的 mirror_prefix 或环境变量 PIXTRACE_MIRROR_PREFIX）
    生成的地址排在最前——用户配置镜像的唯一动机就是直连不通，
    把镜像排在后面等于让用户白等一轮超时。
    """
    config = _load_source_config()

    overrides = config.get("overrides")
    if isinstance(overrides, dict) and isinstance(overrides.get(filename), list):
        base = [str(u) for u in overrides[filename]]
    else:
        base = list(DEFAULT_SOURCES.get(filename, ()))

    prefix = os.environ.get(MIRROR_ENV) or config.get("mirror_prefix") or ""
    prefix = str(prefix).strip()
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    urls: list[str] = []
    if prefix:
        urls.extend(f"{prefix}{u}" for u in base)
    urls.extend(base)
    return urls


def save_source_config(config: dict) -> Path:
    directory = paths.user_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / SOURCES_FILENAME
    target.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


def mirror_prefix() -> str:
    return str(_load_source_config().get("mirror_prefix") or os.environ.get(MIRROR_ENV) or "")


# ------------------------------------------------------------------- 下载
def download(
    url: str,
    dest: Path,
    *,
    expected_sha256: str | None = None,
    progress: Callable[[Progress], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
) -> DownloadResult:
    """下载到 dest。失败抛 DownloadError，取消抛 DownloadCancelled。

    先写 `dest.part` 再原子改名，所以 dest 一旦出现就是完整的文件，
    中途断电不会留下一个"看起来正常但内容残缺"的模型。
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")

    started = time.perf_counter()
    last_error: Exception | None = None
    resumed_from = part.stat().st_size if part.is_file() else 0

    for attempt in range(1, retries + 1):
        try:
            _fetch_once(url, part, progress, cancelled, timeout)
            if expected_sha256:
                actual = sha256_of(part)
                if actual.lower() != expected_sha256.lower():
                    # 内容已确定是坏的，续传无意义，删掉重来
                    part.unlink(missing_ok=True)
                    raise DownloadError(
                        f"校验失败：期望 {expected_sha256[:16]}…，实际 {actual[:16]}…"
                    )
        except DownloadCancelled:
            raise
        except (OSError, urllib.error.URLError, DownloadError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            _interruptible_sleep(RETRY_BACKOFF ** (attempt - 1), cancelled)
            continue
        else:
            size = part.stat().st_size
            os.replace(part, dest)
            if progress:
                progress(Progress(size, size, size / max(time.perf_counter() - started, 1e-6), resumed_from))
            return DownloadResult(
                path=dest,
                bytes_written=size,
                resumed_from=resumed_from,
                elapsed_s=time.perf_counter() - started,
                url=url,
            )

    detail = f"{type(last_error).__name__}: {last_error}" if last_error else "未知错误"
    raise DownloadError(f"下载失败（已尝试 {retries} 次）：{url}\n{detail}") from last_error


def fetch_model(
    spec,
    *,
    dest_dir: Path | None = None,
    progress: Callable[[Progress], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    on_source: Callable[[str], None] | None = None,
    retries: int = DEFAULT_RETRIES,
) -> DownloadResult:
    """按候选源依次尝试，全部失败才报错。"""
    directory = Path(dest_dir) if dest_dir else paths.models_cache_dir()
    target = directory / spec.filename
    urls = sources_for(spec.filename)
    if not urls:
        raise DownloadError(
            f"没有为 {spec.filename} 配置下载源。可在 {paths.user_data_dir() / SOURCES_FILENAME} "
            "中配置 overrides，或使用「手动导入」从本地选择已下载的模型文件。"
        )

    errors: list[str] = []
    for url in urls:
        if cancelled and cancelled():
            raise DownloadCancelled()
        if on_source:
            on_source(url)
        try:
            return download(
                url,
                target,
                expected_sha256=spec.sha256,
                progress=progress,
                cancelled=cancelled,
                retries=retries,
            )
        except DownloadCancelled:
            raise
        except DownloadError as exc:
            errors.append(str(exc))

    joined = "\n\n".join(errors)
    raise DownloadError(
        f"{spec.filename} 的所有下载源均失败：\n\n{joined}\n\n"
        "如果是网络受限，可在「设置下载源」里填写镜像前缀后重试，"
        "或手动下载该文件后用「手动导入」导入。"
    )


# ------------------------------------------------------------------ 内部
def _fetch_once(
    url: str,
    part: Path,
    progress: Callable[[Progress], None] | None,
    cancelled: Callable[[], bool] | None,
    timeout: float,
) -> None:
    offset = part.stat().st_size if part.is_file() else 0
    response, offset = _open(url, offset, timeout)

    with response:
        total = _content_total(response, offset)
        mode = "ab" if offset else "wb"

        downloaded = offset
        last_emit = 0.0
        started = time.perf_counter()
        with part.open(mode) as fh:
            while True:
                if cancelled and cancelled():
                    raise DownloadCancelled()
                block = response.read(CHUNK)
                if not block:
                    break
                fh.write(block)
                downloaded += len(block)

                now = time.perf_counter()
                if progress and now - last_emit >= PROGRESS_INTERVAL:
                    last_emit = now
                    progress(
                        Progress(
                            downloaded,
                            total,
                            (downloaded - offset) / max(now - started, 1e-6),
                            offset,
                        )
                    )

    if progress:
        elapsed = max(time.perf_counter() - started, 1e-6)
        size = part.stat().st_size
        progress(Progress(size, total if total > 0 else size, (size - offset) / elapsed, offset))


def _open(url: str, offset: int, timeout: float):
    """打开流。返回 (response, 实际起始偏移)。"""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # 416：本地分片已经超出服务端文件长度（分片坏了或文件已更新），从零重来
        if offset and exc.code == 416:
            exc.close()
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            return urllib.request.urlopen(request, timeout=timeout), 0
        raise

    if offset and getattr(response, "status", 200) != 206:
        # 服务端不支持 Range，返回了 200 全量：本地分片作废，从头写
        return response, 0
    return response, offset


def _content_total(response, offset: int) -> int:
    headers = response.headers
    content_range = headers.get("Content-Range")  # bytes 100-999/1000
    if content_range and "/" in content_range:
        tail = content_range.rsplit("/", 1)[-1].strip()
        if tail.isdigit():
            return int(tail)
    length = headers.get("Content-Length")
    if length and length.strip().isdigit():
        return offset + int(length.strip())
    return -1


def _interruptible_sleep(seconds: float, cancelled: Callable[[], bool] | None) -> None:
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if cancelled and cancelled():
            raise DownloadCancelled()
        time.sleep(min(0.1, max(0.0, deadline - time.perf_counter())))


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024 or unit == "GB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"
