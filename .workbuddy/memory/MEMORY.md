# 项目长期笔记

## 项目：PixTrace（免费去背景工具，原名 nobg）

- 目录：`D:/WorkBuddy Date/2026-10-08-22-28-54/`
- 定位：Windows 桌面端、本地离线、**开源发布（MIT）**、批量抠图
- 方案文档：`PixTrace-技术方案.md`
- **产品名 PixTrace**（2026-10-09 用户确定，替换原 nobg）。命名分层：
  用户可见名（窗口标题/关于/文档/zip/exe）= `PixTrace`；
  代码标识（Python 包名、CLI prog、logger、线程名、AppData 目录、环境变量前缀）= 小写 `pixtrace`；
  配置文件 `build/pixtrace.spec`、图标 `assets/pixtrace.{ico,png}`。
  相关标识：exe `PixTrace.exe`、交付物 `dist/PixTrace-<版本>-portable.zip`、
  AppData 目录 `%LOCALAPPDATA%/pixtrace`、环境变量 `PIXTRACE_MODEL_DIR` / `PIXTRACE_MIRROR_PREFIX`、
  CLI 默认输出目录 `_PixTrace`。

### 不可动摇的约定

1. **开源发布 → 许可红线**：任何依赖与模型权重必须是 MIT / Apache-2.0 / BSD 级别；
   永久排除 BRIA RMBG 系列（CC BY-NC 4.0，禁商用）。
2. **不用 PyTorch**（打包体积）、**不用 rembg 作运行时**（依赖冗余）、**不用 OpenCV**（wheel 含 LGPL FFmpeg）。
   技术栈固定为：Python 3.11+ / onnxruntime / PySide6 / Pillow / numpy / PyInstaller。
3. 模型只从原作者的官方仓库获取（U^2-Net、DIS），记录 commit + sha256；
   ONNX 由项目内 `scripts/export_onnx.py` 自行导出，保证可复现。
4. 并发模型：ProcessPoolExecutor，每进程 1 个 InferenceSession 且 intra_op_num_threads=1。
5. 打包使用 PyInstaller **onedir**（非 onefile）。
6. 首版明确不做：alpha matting、GPU 加速、手动修边、视频。

### 协作约定（沿用用户既有偏好）

- **方案先行**：讨论阶段只出方案文档，用户确认前不建工程、不装依赖、不写代码。
- **只交付免安装便携版**（2026-10-09 用户明确要求「以后只给我便携版」）：
  交付物只给 `dist/PixTrace-<版本>-portable.zip`；不构建、不交付安装包，也不在交付清单里列 setup.exe。
  `build/installer.iss` 与 `--installer` 参数保留在仓库（可选能力），但默认不启用、不主动提供。
- 交付目录是 **`E:\桌面文件`**（用户真实桌面，不再放 C:\Users\Administrator\Desktop）。
- 打包/交付时 `present_files` 第一个给便携版 zip。

### 当前进度（2026-10-09 更新）

- **v0.3.7 界面质感改造（A+B 档，用户确认后实施）**：冷灰新色板（面板/底亮度差 3%→8%）、
  面板与按钮顶部 1px 高光、统一圆角（8/6）、按钮 30px 高、主按钮边缘高光、渐变进度条、
  拖拽区虚线→实线、列表行高 30 + 凹槽底 + 悬停高亮（去交替行）、耗时列等宽字体、
  空状态图标渐变圆角小卡；新增 app/ui/effects.py（QGraphicsDropShadowEffect：
  卡片级 radius10 会被父级裁剪、弹出层 radius22 用于 QMenu）。QSS 坑：
  QPushButton 全局 focus 蓝框会常亮（删）；::item:selected 加 border-left 会让列间竖线（删）。
- **项目已 git init**（基线 21a65b1 = v0.3.6；v0.3.7 = 9340360）。.gitignore 排除
  models/*.onnx、dist/、build/pixtrace/、.shots/、demo/。**此后大改 UI 先提交再改。**
- **v0.3.6 默认窗口 860×560**（=最小尺寸）。主窗口其实一直有几何记忆（window/geometry）；
  默认尺寸一改，记忆键必须翻代（geometry → geometry2，_restore_state 删旧键），
  否则老用户存的 1080×720 会盖掉新默认。
  shot_gui.py 支持 PIXTRACE_SHOT_SIZE 环境变量、输出名带尺寸后缀、截图前清几何记忆；
  --uicheck 改验真实默认尺寸（不再硬编码 resize）。
- **v0.3.3-v0.3.5 界面微调**：删菜单栏（收进工具条「设置▾」）；开始/取消/进度/耗时
  上移到设置行尾（settings_panel.append_action）；底部整行留给 GitHub 链接+赞赏
  （GITHUB_URL 与 assets/support.png 仍是占位）；空状态整块内容区当拖拽区（app/ui/dropzone.py）。
- **v0.3.2 体积精简**：解压 344.6→312.2 MB、zip 227.3→213.7 MB。
  spec 里 `DROP_NAMES`/`DROP_PREFIXES`/`KEEP_TRANSLATIONS` + `_prune(a.binaries)` 剔除
  opengl32sw.dll、Qt 网络栈、Qt SVG、qdirect2d、PIL/_avif、非中文 translations（共 32.4 MB）。
  **大改 spec 剔除项后必须跑 `--uicheck`**（新增，offscreen 渲染主窗口落盘 PNG）——
  --selftest 不创建 QApplication，测不出「窗口起不来」。
  体积构成：isnet 170 MB / Qt 52 / onnxruntime 36 / numpy 26 / Pillow 5 / Python 21。
- **v0.3.1 界面回退**：苹果风界面被用户否定（「太丑」），确认**完整回退到 v0.2.0 旧观感**。
  重写 style.py（VS Code 暗色 #1e1e1e/#3b82f6 单主题，保留 CHECKER_*/OK_TEXT 令牌名 →
  preview/model_dialog 零改动）、settings_panel.py（radio+色块表单形态）、
  main_window.py（菜单栏/工具条/44px DropBar/带表头交替行表格/底部动作条）。
  删除 title_bar/dropzone/thumbs/status_delegate/icons.py，主题切换机制移除。
  保留：PixTrace 品牌、LOGO（窗口图标+关于页）、smoke_gui.py 零改动兼容。
  **项目无 git，回退靠 demo/ 旧截图 + 方案文档「现状盘点」重写。大改 UI 前先 git init。**
- **v0.2.0 极简版**：界面只留两个功能（去背景透明 / 换纯色底）+ 保存位置。
  固定高精档 isnet（DEFAULT_MODEL_KEY），默认输出与原图同文件夹（`-无背景` 后缀）。
  新增 defringe 去色染（std<18 门槛，证件照换底无蓝边，残留 8132→98 像素）。
  CLI 保留全部能力，默认档位 quality。
- 运行环境：`C:/Users/Administrator/.workbuddy/binaries/python/envs/nobg`（onnxruntime 1.30 + PySide6 6.11 + PyInstaller 6.22），模型在项目 `models/`。
- 构建：`python scripts/build.py --selftest --portable`（不加 `--installer`）；重建前需手动删 dist/ 旧目录
  （本环境批量删除保护会拦截 PyInstaller 的清空操作）。
- 项目内不可违背的实测结论（写死在代码注释里）：isnet 归一化用 0.5/1.0 而非 ImageNet；
  isnet 批量必须 1 进程×默认线程（intra=1 慢 6 倍），u2netp 用 6 进程×intra=1；预处理用 letterbox；
  冻结入口必须最外层 freeze_support()；便携版以 portable.txt 标记判定；
  QSettings 的 panel/state_json 会跨运行渗漏，自动化截图/冒烟脚本开头必须清除；
  TaskStatus 无 RUNNING 成员；QTreeWidgetItem.setForeground 要传 QBrush 不能传 str。
- 本机装大包用 uv（`C:/Users/Administrator/.local/bin/uv.exe` + 阿里源），pip 极慢。

### 下一步（M5 发布）

- `scripts/export_onnx.py` 自行导出 ONNX（许可链条收紧，方案 §2.2 承诺项）
- DEFAULT_SOURCES 换成自有 GitHub Release 地址；README 补截图
- 发布产物只有便携版 zip（发布说明里不提安装包）
