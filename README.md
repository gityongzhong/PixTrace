# PixTrace · 去背景

免费、开源（MIT）、纯本地推理的去背景工具。图片不经过任何网络，断网可用。

**只做两件事**：

1. **去掉背景**，输出带透明通道的 PNG
2. **换成纯色背景**（任意取色），用于证件照换底等场景

## 特性

- **极简界面**：拖入图片 → 选背景 → 开始处理，没有多余选项
- **高精模型**：内置 isnet-general-use（DIS），发丝与复杂边缘干净
- **边缘去色染（defringe）**：自动反解边缘半透明像素的纯前景色，
  蓝底证件照换红底后**没有蓝边**（背景均匀时自动启用，复杂背景自动跳过）
- **批量**：拖入文件夹即递归处理，任务列表实时显示状态与耗时
- **保存省心**：默认与原图放在同一文件夹（文件名加 `-无背景` 后缀，不覆盖原图），
  也可另存到指定文件夹；双击任务可打开原图-结果对比预览
- 全部推理基于 ONNX Runtime CPU，无 PyTorch、无云 API

## 快速开始

```bash
# 1. 环境（Python 3.11+）
python -m venv .venv
.venv\Scripts\pip install onnxruntime numpy pillow

# 2. 模型（放到 models/ 目录，见下文「模型文件」）

# 3. 命令行使用
python cli.py 照片.jpg                    # 结果与照片并排（照片-无背景.png）
python cli.py 照片.jpg -b color --color 255,0,0    # 换成红底
python cli.py 图片夹/ --alongside          # 批量，结果与原图并排
python cli.py 图片夹/ -o 输出目录/          # 批量，另存到指定目录

# 4. 或者用图形界面
python app/main.py
```

## 图形界面

拖入图片或文件夹 → 选背景（透明 / 纯色）→ 点「开始处理」：

- **背景**：透明，或纯色（点击色块任意取色）
- **保存到**：默认「原图所在文件夹」；点开可改存指定文件夹
- 任务列表显示状态（等待/完成/失败）与单张耗时；双击任意任务打开
  **原图-结果对比预览**，中间分割线可拖动；Delete 键移除选中项
- 失败项在列表中标红，再次点「开始处理」即可重跑（已成功的会自动跳过）
- 同名结果直接覆盖更新：改完背景色再点一次，拿到的就是最新结果
- **模型管理**（Ctrl+M）：模型缺失时可在程序内下载（断点续传、sha256 校验、
  失败重试、可配镜像），或从本地手动导入；完全离线的机器走导入路径即可

## 免安装便携版（默认且唯一的交付形态）

本项目只交付**免安装便携版**，不提供安装包。解压即用，不写注册表、不写系统目录：

```
PixTrace-<版本>-portable.zip        （约 214 MB）
├─ PixTrace.exe                     双击运行
├─ portable.txt                 便携模式标记，请勿删除
├─ 使用说明.txt
├─ models/                      两档模型已内置，离线可用
└─ _internal/                   运行库
```

便携模式下，下载的模型与日志同样保存在程序目录内（`models/`、`logs/`），
整个文件夹拷到 U 盘或其他电脑即为完整状态；删除文件夹即完成卸载。

## 为什么这么大（约 214 MB）

一半是 AI 模型，一半是「把整个运行环境装进包里」：

| 部分 | 解压后 | 说明 |
|---|---|---|
| `isnet-general-use.onnx` | 170 MB | 高精抠图模型（DIS，1024×1024 输入）——发丝级边缘的代价，无进一步压缩空间 |
| Qt / PySide6 | 52 MB | 界面库（已剔除约 20 MB 用不到的软件 OpenGL 兜底 `opengl32sw.dll`） |
| ONNX Runtime | 36 MB | 推理引擎 |
| numpy + OpenBLAS | 26 MB | 数学库；Windows 版 numpy 强制捆绑 OpenBLAS，去不掉 |
| Pillow | 5 MB | 图像读写（已剔除 7.5 MB 的 AVIF 编解码插件） |
| Python 运行时 + 程序 | 21 MB | 解释器、标准库与主程序 |

免安装意味着这些依赖必须自带，这是 Python 桌面程序的固有成本（同类工具普遍
150–300 MB，带 PyTorch 的通常在 1 GB 以上）。

精简规则写在 `build/pixtrace.spec` 的 `DROP_NAMES` / `DROP_PREFIXES` 里，每一项都注明了剔除依据。
压缩后收益小于解压收益（解压省 32 MB，zip 只省 13 MB），因为 DLL 本身压缩率有限。

想显著更小只有两条路，且都与「离线 + 高精」冲突：只内置 4.4 MB 的 `u2netp` 极速档
（包约 60 MB，发丝与半透明边缘质量明显下降）；或让高精模型改为首次运行联网下载
（包约 55 MB，失去离线开箱即用）。本项目选择全内置。

## 从源码构建

```bash
pip install pyinstaller
python scripts/build.py --selftest --portable    # onedir 构建 + 产物自检 + 便携版 zip
```

| 产物 | 说明 |
|---|---|
| `dist/PixTrace-<版本>-portable.zip` | **正式交付物**：免安装便携版（两档模型全带，214 MB） |
| `dist/PixTrace/` | 中间产物：onedir 目录版，实测 **142 MB**（含极速档模型），也是上面 zip 的内容 |
| `dist/PixTrace-<版本>-setup.exe` | 可选：Inno Setup 安装包，需自行追加 `--installer` 且本机装有 [Inno Setup 6](https://jrsoftware.org/isinfo.php)；发行版不分发此项 |

要点：

- 打包用 **onedir** 而非 onefile：启动快，且 PySide6 的 Qt 动态库保持可替换形态（LGPL 合规更干净）
- `--selftest` 会对构建产物跑**无人值守自检**：模型定位 → 合成素材 → 多进程批处理 → 输出 alpha 校验，
  结果写入 `dist/selftest.json`。冻结环境最容易坏的是多进程与资源路径，只有真实 exe 能暴露这类回归
- `--uicheck [out.png]` 渲染主界面并落盘 PNG（无头 offscreen），用于验证界面层依赖完整——
  精简运行库这类改动一旦出错就是「窗口起不来」，而 `--selftest` 不创建 QApplication，测不到这一层
- 品牌资产由 `scripts/make_brand_assets.py` 从 `assets/logo-source.png`（设计源稿）派生：
  `pixtrace.ico`（16–256 全尺寸）、`pixtrace.png`、`logo-mark.png`（标题栏）、`logo-full.png`
- 安装包向导暂用 Inno 默认英文：第三方中文 .isl 属可执行脚本（可含 [Code] 段），未经审计不进构建链

## 命令行参数

| 参数 | 说明 |
|---|---|
| `inputs` | 图片文件或目录，可混合多个 |
| `-m quality\|fast` | 模型档位，默认 quality（高精） |
| `-f png\|webp\|jpg` | 输出格式，默认 png |
| `-b transparent\|color\|image\|blur` | 背景类型（图形界面只暴露前两种） |
| `--color R,G,B` | 纯色背景颜色，默认白色 |
| `--bg-image 路径` | 背景贴图路径（配合 `-b image`） |
| `-o 目录或文件` | 输出位置；单文件输入时若以图片后缀结尾则视为输出文件名 |
| `--alongside` | 输出到原图所在文件夹（文件名加 `-无背景` 后缀），与界面默认一致 |
| `--flat` | 不保留子目录结构 |
| `--workers N` | 并发进程数（默认按档位自动：fast=6 进程，quality=1 进程） |
| `--feather N` | 遮罩边缘羽化半径（像素） |
| `--overwrite` | 覆盖已存在的输出 |
| `-v` | 调试日志 |

## 性能（实测）

12 核桌面 CPU，纯推理耗时（不含图片读写）：

| 档位 | 单图（默认线程） | 批量配置 | 备注 |
|---|---|---|---|
| 极速 u2netp | 约 250 ms | 6 进程 × 单线程 | 批量吞吐最高 |
| 高精 isnet | 约 1.2 s | 1 进程 × 全核 | 大模型吃多线程，限制单线程反而慢 6 倍 |

> 大模型与小模型的最优并发策略相反，这是实测得出的，已在 `ModelSpec.worker_intra` 中固化。

## 模型文件

运行需要两个 ONNX 模型。图形界面里点「管理模型」即可下载或导入；
源码运行时放到 `models/` 目录（查找顺序：`PIXTRACE_MODEL_DIR` → 打包资源目录 →
程序目录 `models/` → `%LOCALAPPDATA%/pixtrace/models`）：

| 文件 | 大小 | 来源 | 许可 |
|---|---|---|---|
| `u2netp.onnx` | 4.4 MB | [U^2-Net](https://github.com/xuebinqin/U-2-Net) | Apache-2.0 |
| `isnet-general-use.onnx` | 170 MB | [DIS](https://github.com/xuebinqin/DIS) | Apache-2.0 |

详见 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)。

## 工程说明

- 预处理用 **letterbox**（等比缩放 + 补边），不做直接拉伸——宽幅图直接拉伸会让主体几何变形、遮罩出现切边伪影（有对照实验数据，见 `scripts/probe_norm.py`）
- 每个模型的输入尺寸/归一化常数**来自实测**（`scripts/inspect_onnx.py`）与官方推理脚本核对，不凭家族经验推广（u2net 用 ImageNet 常数，isnet 用 0.5/1.0，同家族也不一样）
- **边缘去色染**：背景均匀（逐通道 std < 18，实测证件照蓝底 ≈7.5、复杂霓虹背景 ≈44）时，
  按 `I = a·fg + (1-a)·bg` 反解半透明像素的纯前景色，消除换底色后的原背景色边缘；
  复杂背景自动跳过，同一输入固定随机种子保证结果可复现
- 并发单位是进程；进程数与线程数的配比按模型档位实测确定

## 许可

本项目代码以 MIT 许可发布。模型权重与第三方组件的许可见 `THIRD_PARTY_LICENSES.md`。
