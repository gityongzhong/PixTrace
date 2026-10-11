"""一键构建与打包。

用法：
    python scripts/build.py                 # PyInstaller onedir 构建
    python scripts/build.py --portable      # 构建后追加便携版 zip
    python scripts/build.py --installer     # 构建后用 Inno Setup 编译安装包
    python scripts/build.py --selftest      # 构建后对 exe 跑无人值守自检

产物：
    dist/PixTrace/                    onedir 目录（可直接运行）
    dist/PixTrace-<版本>-portable.zip 便携版
    dist/PixTrace-<版本>-setup.exe    安装包
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = Path(sys.executable)
ISCC_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    Path.home() / "AppData/Local/Programs/Inno Setup 6/ISCC.exe",
]


def run(cmd: list[str]) -> int:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.call([str(c) for c in cmd])


def app_version() -> str:
    """版本号只在一处维护（pyproject.toml），这里读取它。"""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.0.0"


def dir_size(path: Path) -> str:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return f"{total / 1048576:.0f} MB"


def build() -> int:
    return run([
        VENV_PY, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        str(ROOT / "build" / "pixtrace.spec"),
    ])


def check_selftest() -> int:
    exe = ROOT / "dist" / "PixTrace" / "PixTrace.exe"
    if not exe.is_file():
        print(f"找不到 {exe}", file=sys.stderr)
        return 1
    out = ROOT / "dist" / "selftest.json"
    code = run([exe, "--selftest", str(out)])
    report = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {"ok": False}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"selftest {'通过' if report.get('ok') else '失败'} (exit={code})")
    return 0 if report.get("ok") and code == 0 else 1


def make_portable(version: str) -> int:
    """产出免安装便携版 zip。

    布局（解压即用，全部数据留在文件夹内，不写注册表/系统目录）：
        PixTrace.exe
        portable.txt        便携模式标记（应用据此把模型与日志写在本目录）
        使用说明.txt
        models/             内置全部模型（极速 + 高精）
        _internal/          运行库

    极速档本来就在 _internal/models 里；这里把它挪到外层 models/ 统一存放，
    高精档也从项目 models/ 一并带上——应用内下载 171MB 在慢网环境下不现实。
    """
    src = ROOT / "dist" / "PixTrace"
    if not src.is_dir():
        print(f"找不到 {src}，先执行构建", file=sys.stderr)
        return 1

    stage = ROOT / "dist" / f"PixTrace-{version}-portable"
    if stage.exists():
        try:
            shutil.rmtree(stage)
        except OSError as exc:
            print(f"无法清理旧的便携版目录 {stage}：{exc}\n请手动删除后重试。", file=sys.stderr)
            return 1
    shutil.copytree(src, stage)

    bundled = stage / "_internal" / "models"
    target = stage / "models"
    target.mkdir(parents=True, exist_ok=True)
    if bundled.is_dir():
        for onnx in bundled.glob("*.onnx"):
            shutil.move(str(onnx), target / onnx.name)
        shutil.rmtree(bundled)
    for onnx in (ROOT / "models").glob("*.onnx"):
        shutil.copy2(onnx, target / onnx.name)

    (stage / "portable.txt").write_text(
        "便携模式标记文件，请勿删除。\n"
        "存在此文件时，PixTrace 会把下载的模型与日志保存在本文件夹内。\n",
        encoding="utf-8",
    )
    (stage / "使用说明.txt").write_text(
        f"PixTrace · 去背景  免安装便携版 v{version}\n"
        + "=" * 36 + "\n\n"
        "用法\n"
        "  双击 PixTrace.exe → 把图片或文件夹拖进窗口 → 选背景（透明 / 纯色）\n"
        "  → 点「开始处理」。\n"
        "  结果默认保存在原图所在文件夹，文件名加「-无背景」后缀，不覆盖原图；\n"
        "  也可点「保存到」改存到指定文件夹。\n\n"
        "说明\n"
        "  · 内置高精模型（isnet），发丝边缘干净，单张约 1-3 秒\n"
        "  · 输出 PNG：透明模式带透明通道，纯色模式为不透明图像\n"
        "  · 同名结果会被覆盖更新：点一次「开始处理」，得到的就是最新结果\n"
        "  · 全部在本机处理，图片不联网、不上传\n\n"
        "模型\n"
        "  高精档（isnet）已内置在 models/ 目录，离线可用。\n"
        "  下载的模型与日志同样保存在本文件夹，整个目录可整体拷贝到其他机器或 U 盘。\n\n"
        "删除\n"
        "  直接删除本文件夹即可，不会留下系统残留。\n",
        encoding="utf-8",
    )

    target_zip = ROOT / "dist" / f"PixTrace-{version}-portable.zip"
    if target_zip.exists():
        target_zip.unlink()
    script = (
        "Add-Type -AssemblyName System.IO.Compression.FileSystem;"
        f"[System.IO.Compression.ZipFile]::CreateFromDirectory("
        f"'{stage}', '{target_zip}', 'Optimal', $false)"
    )
    code = run(["powershell", "-NoProfile", "-Command", script])
    if code == 0 and target_zip.is_file():
        print(f"便携版：{target_zip}  ({target_zip.stat().st_size / 1048576:.0f} MB)")
        print(f"便携版目录：{stage}")
    return code


def make_installer(version: str) -> int:
    iscc = next((p for p in ISCC_CANDIDATES if p.is_file()), None)
    if iscc is None:
        print("找不到 Inno Setup（ISCC.exe），请先安装：winget install JRSoftware.InnoSetup",
              file=sys.stderr)
        return 1
    return run([
        iscc,
        f"/DAppVersion={version}",
        f"/O{ROOT / 'dist'}",
        str(ROOT / "build" / "installer.iss"),
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portable", action="store_true", help="构建后产出便携版 zip")
    parser.add_argument("--installer", action="store_true", help="构建后用 Inno Setup 编译安装包")
    parser.add_argument("--selftest", action="store_true", help="构建后对 exe 跑自检")
    parser.add_argument("--skip-build", action="store_true", help="跳过构建，只做后续步骤")
    args = parser.parse_args()

    version = app_version()
    print(f"版本 {version}")

    code = 0 if args.skip_build else build()
    if code != 0:
        return code

    out_dir = ROOT / "dist" / "PixTrace"
    if out_dir.is_dir():
        print(f"构建完成：{out_dir}  ({dir_size(out_dir)})")

    if args.selftest:
        code = check_selftest()
    if code == 0 and args.portable:
        code = make_portable(version)
    if code == 0 and args.installer:
        code = make_installer(version)
    return code


if __name__ == "__main__":
    sys.exit(main())
