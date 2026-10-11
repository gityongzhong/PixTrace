"""日志配置。

CLI 走标准输出；GUI（尤其是打包后的冻结版）没有控制台，stderr 写出去就丢了，
所以额外挂一个滚动文件处理器到 %LOCALAPPDATA%/pixtrace/logs/pixtrace.log。

这一步不是可选项：用户装了程序报错时，没有日志就只能靠猜。
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from . import paths

_LOGGER_NAME = "pixtrace"
_MAX_BYTES = 1 << 20  # 1 MB × 3 份
_BACKUP_COUNT = 3


def _file_log_path() -> Path:
    return paths.log_dir() / "pixtrace.log"


def setup_logging(verbose: bool = False, *, to_file: bool | None = None) -> logging.Logger:
    """配置根 logger。to_file=None 时冻结环境自动启用文件日志。"""
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    if to_file is None:
        to_file = paths.is_frozen()

    if not paths.is_frozen():
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(stream)

    if to_file:
        try:
            path = _file_log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            rotating = logging.handlers.RotatingFileHandler(
                path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
            )
            rotating.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s [%(process)d] %(name)s: %(message)s")
            )
            logger.addHandler(rotating)
        except OSError:
            # 日志目录不可写不应该让程序起不来
            pass

    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def log_path() -> Path:
    return _file_log_path()


def install_excepthook() -> None:
    """未捕获异常落盘。打包后没有控制台，崩溃现场只能靠这里留下。"""

    def hook(exc_type, exc_value, exc_tb):
        get_logger().critical("未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
        # 冻结的 windowed 版里 stderr 可能是 None，别让兜底代码自己再抛一次
        if sys.__excepthook__ is not None and sys.stderr is not None:
            try:
                sys.__excepthook__(exc_type, exc_value, exc_tb)
            except Exception:  # noqa: BLE001
                pass

    sys.excepthook = hook
