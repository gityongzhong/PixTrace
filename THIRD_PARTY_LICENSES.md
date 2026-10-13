# 第三方组件与许可清单

本项目为 MIT 许可。以下是分发时必须随附的全部第三方组件及其许可。

## 模型权重

### u2netp.onnx（4.4 MB）

- **来源**：ONNX 转换版取自 https://github.com/danielgatis/rembg/releases/tag/v0.0.0
- **原始模型**：U^2-Net（https://github.com/xuebinqin/U-2-Net），Apache License 2.0
- **md5**：`8e83ca70e441ab06c318d82300c84806`（与 rembg release 声明一致）
- **sha256**：`309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8`

### isnet-general-use.onnx（170 MB）

- **来源**：ONNX 转换版取自 https://github.com/danielgatis/rembg/releases/tag/v0.0.0
- **原始模型**：IS-Net / DIS（https://github.com/xuebinqin/DIS），Apache License 2.0
- **md5**：`fc16ebd8b0c10d971d3513d564d01e29`（与 rembg release 声明一致）
- **sha256**：`60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a`

> 说明：模型权重本身为 Apache-2.0。当前 ONNX 文件使用 rembg 项目提供的转换版（该转换
> 脚本同为开源）；发布前计划改为自行从官方 PyTorch 权重导出（`scripts/export_onnx.py`，
> 待实现），进一步收紧许可与可复现性链条。

### 被排除的模型

- BRIA RMBG-1.4 / RMBG-2.0：**CC BY-NC 4.0（禁止商用）**，与本项目许可目标冲突，明确不使用。

## Python 依赖（随程序分发）

| 包 | 许可 | 用途 |
|---|---|---|
| onnxruntime | MIT | 推理引擎 |
| numpy | BSD-3-Clause | 数值计算 |
| Pillow | MIT-CMU (HPND) | 图像读写与合成 |
| PySide6（Qt6） | LGPLv3 | 图形界面 |

### PySide6 / Qt 的 LGPL 合规说明

以**动态链接**方式分发（PyInstaller onedir，Qt 的 DLL 保持独立的可替换文件），
未静态链接、未修改 Qt 源码。用户可以用自行构建的同版本 Qt 库替换程序目录中的
对应文件。LGPLv3 许可全文见
https://www.gnu.org/licenses/lgpl-3.0.html ，
Qt 使用的第三方组件清单见
https://doc.qt.io/qt-6/qt-attribution.html 。

## 界面资源

| 资源 | 来源 | 许可 |
|---|---|---|
| assets/github.png（右下角仓库链接图标） | GitHub Octicons「mark-github」16×16 路径（https://github.com/primer/octicons），经 `scripts/make_git_icon.py` 渲染生成 | MIT |

## 构建工具（不随程序分发，仅构建期使用）

| 包 | 许可 | 说明 |
|---|---|---|
| PyInstaller | GPL v2 + 引导程序例外 | 其引导程序（bootloader）会被嵌入可执行文件。PyInstaller 许可明确允许：经它打包的**输出程序**不受 GPL 约束，可采用任意许可（含本项目的 MIT） |
| Inno Setup | Inno Setup License（基于 BSD 风格） | 安装包制作工具，仅本机构建用，其代码不进入产物 |

## 刻意未使用

| 组件 | 原因 |
|---|---|
| PyTorch | 打包体积 1.5GB+，仅开发期导出 ONNX 时在开发机使用 |
| opencv-python | wheel 内置 FFmpeg（LGPL），纯图片处理场景属多余许可负担 |
| rembg（运行时） | 依赖链冗余；仅参考其模型转换与预处理常数 |
| alpha matting（pymatting/numba） | 依赖重，暂以可调羽化替代 |
| 第三方 Inno Setup 中文语言文件 | .isl 可包含可执行脚本段，未经审计不进构建链 |
