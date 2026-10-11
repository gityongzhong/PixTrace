# PixTrace · 免费去背景工具 技术方案

> 状态：待评审（评审通过后再进入编码）
> 目标形态：Windows 桌面端 / 本地离线推理 / 开源发布（MIT）

---

## 1. 项目定位

一个**完全免费、可商用、纯本地离线**的批量抠图工具。用户拖入图片或文件夹，模型在前端神经网络推理出 alpha 遮罩，输出透明 PNG 或替换背景后的图片。

三条硬约束（来自需求确认）：

| 约束 | 含义 |
|---|---|
| 本地离线 | 图片零上传，不依赖任何云 API，断网可用 |
| 全链路宽松许可 | 代码 MIT；依赖与模型权重必须是 MIT / Apache-2.0 / BSD 等宽松许可，禁止混入 CC BY-NC |
| 桌面批量 | 核心价值是「一次处理几百上千张」，不是单张精修 |

---

## 2. 许可合规（本方案的第一优先项）

因为是开源发布，许可链条必须从代码一路干净到模型权重。

### 2.1 代码依赖

| 组件 | 许可 | 说明 |
|---|---|---|
| onnxruntime | MIT | 推理引擎，CPU 版约 15-30MB |
| PySide6 | LGPLv3 | 允许 MIT 项目动态链接分发；需随包附 LGPL 全文 |
| numpy | BSD-3-Clause | 张量运算 |
| Pillow | MIT-CMU (HPND) | 图像读写、缩放、合成 |

**刻意不用 OpenCV**：`opencv-python` 的 wheel 内置 FFmpeg（LGPL），对纯图片处理是多余的许可杂音，且体积大。首版统一走 Pillow + numpy，性能不足再评估 `opencv-python-headless`。

**刻意不用 PyTorch**：打包体积 1.5GB+，启动慢，PyInstaller 兼容性差。仅开发机在导出 ONNX 时使用。

**不用 rembg 作为运行时依赖**：它是一个便利封装，但会引入 pymatting、aiohttp 等一串依赖。我们只借用它的**模型文件**思路，推理、预处理、后处理全部自研，保证可控性与依赖最小化。

### 2.2 模型权重（关键红线）

| 模型 | 体积 | 许可 | 来源 |
|---|---|---|---|
| u2netp | 4.7 MB | Apache-2.0 | U^2-Net 官方仓库 `xuebinqin/U-2-Net` |
| u2net | 176 MB | Apache-2.0 | 同上 |
| isnet-general-use | 176 MB | Apache-2.0 | DIS 官方仓库 `xuebinqin/DIS` |
| ~~RMBG-1.4 / RMBG-2.0~~ | - | **CC BY-NC 4.0（禁商用）** | **排除** |
| ~~BiRefNet~~ | - | MIT（许可干净） | 首版不用，模型 224MB+、CPU 太慢，列为后续扩展 |

**执行动作**：
1. 只从上述**原作者的官方仓库**获取权重，不用第三方二次上传的副本；
2. 记录每个权重的 `仓库 URL + commit hash + 文件 sha256`，写入 `THIRD_PARTY_LICENSES.md`；
3. ONNX 文件由 `scripts/export_onnx.py` 在开发机从官方权重自行导出，导出脚本一并开源，保证可复现；
4. 模型文件通过项目自己的 GitHub Release 分发（带 sha256 校验），避免依赖上游仓库长期可用性。

### 2.3 其他资产

- 界面图标：Lucide（ISC）或 Material Symbols（Apache-2.0），全宽松许可；
- 不引入任何非商用字体。

---

## 3. 技术栈

```
Python 3.11+ (Win)
├─ onnxruntime          # CPU 推理，后续可平替 onnxruntime-directml
├─ PySide6              # GUI
├─ Pillow + numpy       # 图像 IO / 缩放 / 合成
└─ PyInstaller          # 打包（建议 onedir，见 §9）
```

选 Python 3.11 而非 3.13：PyInstaller 与 onnxruntime 的 wheel 兼容性在 3.11 上最稳。

---

## 4. 双档模型设计

### 4.1 档位定义

| 档位 | 模型 | 输入尺寸 | 单图耗时（8核CPU，估） | 适用 |
|---|---|---|---|---|
| 极速 | u2netp | 320×320 | 30-80 ms | 海量电商白底图、人像、简单主体 |
| 高精 | isnet-general-use | 1024×1024 | 0.6-2.5 s | 复杂边缘、发丝、半透明物体、前景背景同色 |

界面上一键切换，默认极速档；批处理中途可切档（切换时重建 session，代价约 1s）。

### 4.2 模型注册表

用声明式结构描述每个模型的差异，避免 `if model == ...` 散落各处：

```python
@dataclass(frozen=True)
class ModelSpec:
    key: str                 # "u2netp"
    display: str             # "极速"
    filename: str
    sha256: str
    input_size: int          # 320 / 1024
    mean: tuple[float, ...]  # ImageNet: (0.485, 0.456, 0.406)
    std: tuple[float, ...]   # ImageNet: (0.229, 0.224, 0.225)
    output_index: int        # 多输出时取哪个（u2net/isnet 均取首个）
    resize_input: str        # "bilinear"
    post_resize: str         # mask 回填原尺寸的插值方式
```

> 每个模型的输入尺寸、归一化常数、输出取法**必须**以官方推理脚本为准逐个核对，不靠记忆。接入时会在 `models.py` 旁附来源链接与 commit。

---

## 5. 推理管线

```
读取图片 (Pillow, 保留 EXIF 方向)
   │
   ├─ 预处理
   │   等比缩放到 input_size × input_size（letterbox 或直接拉伸，见待定项 A）
   │   → RGB → float32 / 255 → (x - mean) / std
   │   → HWC → NCHW
   │
   ├─ 推理（onnxruntime InferenceSession.run）
   │   → 输出 alpha map，形状 (1, 1, input_size, input_size)，值域约 [0, 1]
   │
   ├─ 遮罩后处理
   │   取 output_index 对应的输出 → min-max 归一化到 [0,1]
   │   → 缩放到原图尺寸（双线性）
   │   → 可选：对比度增强 / 轻微羽化（纯 numpy，不引入 matting 库）
   │
   └─ 合成
       透明 PNG/WebP：RGBA，alpha = mask
       纯色背景：out = fg * a + color * (1 - a)
       贴图背景：同上，背景图先按 cover 方式缩放到原图尺寸
       原图虚化：背景 = 原图高斯模糊 + 轻微暗化
```

**并发策略**：`onnxruntime` 的 session 内部已多线程，多文件再开线程池会互相抢核，反而更慢。采用 **ProcessPoolExecutor**：

```
workers   = min(os.cpu_count(), 4)          # 可配置
每进程    : 1 个 InferenceSession，intra_op_num_threads = 1
Windows   : spawn 模式，worker 里延迟 import onnxruntime 并全局缓存 session
```

根据档位自适应：极速档可开 4-6 进程；高精档模型 176MB，每进程一份内存（约 300-500MB），默认降到 2 进程。

---

## 6. 模块结构

```
pixtrace/
├─ app/
│  ├─ main.py                  # 入口，QApplication + 异常兜底
│  ├─ ui/
│  │  ├─ main_window.py        # 主窗口：拖拽区 / 任务列表 / 参数栏 / 状态栏
│  │  ├─ preview.py            # 原图-结果 对比预览（可拖动分割线）
│  │  ├─ settings_panel.py     # 档位、输出格式、背景、输出目录、并发数
│  │  └─ style.qss             # 暗色主题（跟随系统可选）
│  ├─ core/
│  │  ├─ models.py             # ModelSpec 注册表
│  │  ├─ engine.py             # InferenceEngine：load(spec) / infer(np_img) -> np_mask
│  │  ├─ preprocess.py
│  │  ├─ postprocess.py
│  │  ├─ compositor.py         # 背景合成
│  │  └─ types.py              # Task / TaskResult / JobOptions
│  ├─ batch/
│  │  ├─ planner.py            # 扫描目录 → 任务列表（去重、过滤扩展名、保留相对路径）
│  │  ├─ worker.py             # 进程池 worker 函数
│  │  └─ job_queue.py          # 调度、进度回调、取消、失败重试
│  └─ infra/
│     ├─ model_store.py        # 模型下载 / sha256 校验 / 本地缓存 / 手动导入
│     ├─ config.py             # QSettings 持久化用户偏好
│     └─ logging.py
├─ scripts/
│  ├─ export_onnx.py           # 开发机一次性导出（需 torch，不进发行包）
│  └─ build.spec               # PyInstaller 配置
├─ models/                     # 不入 git（gitignore）
├─ tests/
├─ LICENSE                     # MIT
├─ THIRD_PARTY_LICENSES.md
└─ README.md
```

---

## 7. 界面与交互

**主流程（三步内完成）**

1. 拖入图片/文件夹（或点选）→ 列表展示缩略图 + 文件名 + 状态
2. 右侧参数栏设一次：档位 / 输出格式 / 背景 / 输出位置 / 并发数
3. 点「开始」→ 进度条 + 实时耗时 + 剩余预估；可暂停、取消

**关键控件**

- 拖拽区支持混合拖入文件与文件夹，文件夹递归扫描；
- 输出位置三选：源目录旁 `_PixTrace` 子目录 / 指定目录（保留相对路径结构）/ 覆盖原文件（默认禁用，需二次确认）；
- 结果列表可按状态筛选（成功 / 失败 / 跳过），失败项可「仅重跑失败项」；
- 双击任一任务 → 对比预览窗口，确认后再决定是否重跑该张。

**不做的事（首版）**：不做手动笔刷修边、不做图层编辑、不做视频。保持工具属性，不滑向修图软件。

---

## 8. 模型分发策略（M4 已实现）

| 方案 | 包体 | 评价 |
|---|---|---|
| 全部随包附带 | ~600MB+ | 下载痛苦，不推荐 |
| 全部首次下载 | ~50MB 安装包 | 首次使用必须联网 |
| **安装包带极速档 + 高精档按需下载** | **~120MB** | **推荐** |

实现要点（落地在 `app/infra/downloader.py` 与 `app/ui/model_dialog.py`）：
- 模型缓存目录：`%LOCALAPPDATA%/pixtrace/models/`；**便携版例外**——程序目录含 `portable.txt`
  标记时改写到程序目录内，保证整个文件夹拷走即完整状态、不写系统目录；
- 下载带 sha256 校验、断点续传（Range）、失败重试（3 次）、进度与取消，`urllib` 标准库实现（不加依赖）；
- 下载源可配置：`%LOCALAPPDATA%/pixtrace/sources.json` 支持 `mirror_prefix` 与按文件覆盖，环境变量 `PIXTRACE_MIRROR_PREFIX` 同效；
- 「手动导入模型」入口：文件名匹配不上时按 sha256 反查档位（用户常把文件改名）；
- 实测：本机走代理 28 KB/s 下载 4.4MB 极速档 162 秒，续传分支、哈希校验、原子落盘（.part → 正式文件）均验证通过。

---

## 9. 打包与分发（M4 已实现，实测数据）

- **PyInstaller `onedir`**（`build/pixtrace.spec`）：实测包体 **175 MB**（含极速档模型、
  PySide6 Essentials、onnxruntime、numpy），比初估的 120MB 略大、远小于全模型随包的 600MB；
- 排除了用不到的 Qt 模块（Qml/Quick/Multimedia/Pdf/OpenGL 等）——这是包体从 270MB 降到 175MB 的主要原因；
- `upx=False`：UPX 会压坏 onnxruntime / Qt 的个别 DLL，不值得赌；
- **便携版**（`scripts/build.py --portable`）：`portable.txt` 标记 + 全模型内置 + 数据写程序目录，解压即用；
- **安装包**：Inno Setup（`build/installer.iss`），支持用户级/机器级安装选择；向导文案暂用 Inno 默认英文——
  第三方中文 .isl 属可执行脚本（可含 [Code] 段），未经审计不进构建链；
- 自检（`PixTrace.exe --selftest`）：冻结版跑模型定位 → 合成素材 → 多进程批处理 → 输出 alpha 校验，
  结果写 JSON。冻结环境最容易坏的多进程与资源路径，只有真实 exe 能暴露。

---

## 10. 性能（M1 实测，12 核桌面 CPU，`scripts/bench.py` 可复现）

纯推理耗时（不含图片读写）：

| 档位 | 单图（默认线程） | 批量 worker 配置 |
|---|---|---|
| 极速 u2netp | 约 250 ms | 6 进程 × intra_op=1：单张 0.8-1.2 s |
| 高精 isnet | 约 1.2 s | 1 进程 × 默认线程 |

> 重要实测结论：大模型与小模型的最优并发策略**相反**。isnet 限制单线程会让推理
> 从 1.2s 劣化到 7.2s（慢 6 倍），因此高精档批量必须保留 ORT 默认多线程、
> 只用 1 进程；极速档则相反。已固化为 `ModelSpec.worker_intra`。

端到端（含读写与 PNG 压缩，素材 2582×3443 ~ 3840×2400 大图）：
- 极速档批量约 1.2-1.7 s/张；高精档批量约 4.5 s/张；小图会显著更快

---

## 11. 里程碑

| 阶段 | 内容 | 产出 |
|---|---|---|
| M1 | 核心引擎：模型注册表 + 预处理/后处理 + 单图 CLI 跑通（两档） | ✅ 可命令行抠图，附基准数据 |
| M2 | 批量调度 + 背景替换 + 输出策略 | ✅ 命令行批量可用 |
| M3 | PySide6 界面：拖拽、列表、参数、进度、对比预览 | ✅ 可交互使用 |
| M4 | 模型下载器 + PyInstaller 打包 + 便携版/安装包 | ✅ 可分发测试版（175MB / 多进程自检通过） |
| M5 | 许可清单核对 + README + 截图 + 发布 Release | 开源发布 |

---

## 12. 待定项（编码前需拍板）

| 编号 | 问题 | 倾向 |
|---|---|---|
| A | 预处理是否 letterbox（保持长宽比 + 补边）？ | 倾向 letterbox。直接拉伸会让遮罩在极端长宽比图上变形，代价是长边有效分辨率下降 |
| B | 输出默认格式 | PNG（无损带 alpha）；提供 WebP 选项省空间 |
| C | 是否支持 CMYK / 16bit TIFF 输入 | 首版转 sRGB 8bit 处理，原格式特性不保留 |
| D | 界面语言 | 首版中文，字符串走 i18n 表，便于后续加英文 |

---

## 13. 明确的非目标（首版不做）

- alpha matting（半透明边缘精修）：需要 pymatting + numba，依赖重、打包麻烦，改为轻量羽化后处理替代；
- GPU 加速（DirectML / CUDA）：CPU 已能满足批量场景，后续作为可选开关加回，架构上预留 `providers` 参数即可；
- 手动修边、图层、视频、批量重命名、云同步。

---

## 14. 风险

| 风险 | 应对 |
|---|---|
| 模型权重许可被上游改动 | 锁定 commit + sha256，必要时自行镜像，在 NOTICE 中说明来源与许可 |
| PySide6 LGPL 合规被挑刺 | onedir 打包保留可替换的动态库，附 LGPL 全文，README 说明替换方法 |
| 模型下载源不稳 | 手动导入入口 + 镜像地址可配置 |
| 无 matting 导致发丝边缘发虚 | 后处理加「边缘羽化强度」滑块，作为质量与速度的折中 |
| 大批量内存峰值过高 | 高精档自动降并发；worker 内流式处理，逐张释放，不累积在内存 |
