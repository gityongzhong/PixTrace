# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（onedir）。

为什么 onedir 而不是 onefile：
1. 启动快：onefile 每次启动要把 200+ MB 解压到临时目录；
2. LGPL 合规：PySide6 的动态库保持可替换形态，用户可以换成自构建版本；
3. 模型外挂：模型作为数据文件放在包内独立目录，将来更新模型不用重发 exe。

为什么 windowed（console=False）还要配 --selftest：无控制台的 GUI 没法在
命令行里验证，自检模式把批处理全链路的结果写到 JSON，让打包产物可以被
机器验证（见 app/main.py）。

构建：python scripts/build.py   （或直接 python -m PyInstaller build/pixtrace.spec）
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

# 随包分发的数据文件。u2netp 只有 4.4MB，直接带上让安装即可用；
# isnet 171MB 走应用内下载器按需获取。
datas = [
    (str(ROOT / "models" / "u2netp.onnx"), "models"),
    (str(ROOT / "assets" / "pixtrace.png"), "assets"),
    (str(ROOT / "assets" / "logo-mark.png"), "assets"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD_PARTY_LICENSES.md"), "."),
    (str(ROOT / "README.md"), "."),
]

# 用不到的 Qt / 标准库模块。排除它们不是为了省几 MB——是这些模块的
# 插件 DLL 会被 hook 一并收进来，个别（如 QtWebEngine）会带出上百 MB。
EXCLUDES = [
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuick3D",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSpatialAudio",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtGraphs",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtUiTools",
    "PySide6.QtHelp",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSerialPort",
    "PySide6.QtBluetooth",
    "PySide6.QtPositioning",
    "PySide6.QtSensors",
    "PySide6.QtTextToSpeech",
    "PySide6.QtVirtualKeyboard",
    "tkinter",
    "unittest",
    "pydoc_data",
    "test",
    "distutils",
]

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

# --------------------------------------------------------------- 体积精简
# PySide6 / Pillow 的 hook 会把「整个安装目录」的动态库与插件搬进来，
# 其中相当一部分本程序永远不会加载。逐项剔除，解压后约省 39 MB。
#
# 剔除依据（每一项都经过实际运行验证，见 README 的「为什么这么大」一节）：
DROP_NAMES = {
    # 软件 OpenGL 兜底（20 MB）：界面全部是 QSS 自绘，从不创建 GL 上下文
    "opengl32sw.dll",
    # Qt 网络栈：本程序不联网。模型下载走 Python 的 urllib + ssl（libssl 保留）
    "Qt6Network.dll",
    "QtNetwork.pyd",
    # Qt SVG：图标是 .ico / .png，界面没有任何 SVG
    "Qt6Svg.dll",
    "qsvg.dll",
    "qsvgicon.dll",
    # 备用平台插件：Windows 上只用 qwindows.dll（qoffscreen 留给 --uicheck）
    "qdirect2d.dll",
    # 用不到的图像格式插件（支持的输入是 PNG/JPG/WebP/BMP/TIFF）
    "qicns.dll",   # macOS 图标
    "qtga.dll",
    "qwbmp.dll",
}
DROP_PREFIXES = (
    "PySide6/plugins/tls/",              # 配合 Qt6Network 一起移除
    "PySide6/plugins/networkinformation/",
)
# Qt 自带的界面翻译只留简体中文，其余 90 多个语言包约 6.2 MB
KEEP_TRANSLATIONS = {"qt_zh_CN.qm", "qtbase_zh_CN.qm"}


def _prune(entries):
    kept, removed = [], []
    for entry in entries:
        dest = str(entry[0]).replace("\\", "/")
        name = dest.rsplit("/", 1)[-1]
        if dest.startswith("PySide6/translations/"):
            keep = name in KEEP_TRANSLATIONS
        elif any(dest.startswith(prefix) for prefix in DROP_PREFIXES):
            keep = False
        elif name.startswith("_avif."):      # Pillow 的 AVIF 编解码（7.5 MB）
            keep = False
        else:
            keep = name not in DROP_NAMES
        (kept if keep else removed).append(entry)

    saved = 0
    for entry in removed:
        try:
            saved += Path(entry[1]).stat().st_size
        except OSError:
            pass
    print(f"[spec] 精简运行库：剔除 {len(removed)} 个文件，约 {saved / 1048576:.1f} MB")
    return kept


a.binaries = _prune(a.binaries)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PixTrace",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 会压坏 onnxruntime / Qt 的个别 DLL，不值得赌
    console=False,
    icon=str(ROOT / "assets" / "pixtrace.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PixTrace",
)
