"""路径解析：区分「应用目录」与「用户数据目录」，同时兼容开发态与冻结态。

冻结（PyInstaller）后 `__file__` 指向的是打包内部路径，不能再用它推算项目根目录。
判断依据统一放在这里，避免各处重复写 `getattr(sys, "frozen", False)`。

- 应用目录：只读资源所在处（onedir 下就是 exe 旁边），随包装一起分发；
- 用户数据目录：可写，模型缓存与日志放这里。装到 Program Files 时应用目录不可写，
  这一点决定了「下载的模型不能放应用目录」。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


# 便携版标记：exe 旁边有这个文件即启用便携模式
PORTABLE_MARKER = "portable.txt"


def is_portable() -> bool:
    """是否运行在便携（免安装）模式。

    便携版的全部可写数据（下载的模型、日志）都留在程序目录里，
    这样整个文件夹拷到 U 盘或另一台机器就是完整可用状态，
    也满足"不写注册表、不写系统目录"的免安装承诺。
    """
    return (app_dir() / PORTABLE_MARKER).is_file()


def _portable_writable() -> bool:
    """便携目录本身可写才走便携数据目录。

    用户把便携包解到 Program Files 这类只读位置时，写不进去，
    必须回退到用户数据目录，否则下载模型会直接报错。
    """
    return is_writable(app_dir())


def app_dir() -> Path:
    """应用目录。

    冻结后：onedir 下是 exe 所在目录（模型、LICENSE 等随包资源在此）；
    开发态：项目根目录。
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_dir() -> Path:
    """打包内部资源目录（onefile 才是临时解包目录；onedir 与应用目录一致）。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return app_dir()


def user_data_dir() -> Path:
    """可写的用户数据目录：Windows 下是 %LOCALAPPDATA%/pixtrace。"""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(base) / "pixtrace"


def models_cache_dir() -> Path:
    if is_portable() and _portable_writable():
        return app_dir() / "models"
    return user_data_dir() / "models"


def log_dir() -> Path:
    if is_portable() and _portable_writable():
        return app_dir() / "logs"
    return user_data_dir() / "logs"


def is_writable(directory: Path) -> bool:
    """目录（或最近的已存在父目录）是否可写。"""
    probe = directory
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    return os.access(probe, os.W_OK)
