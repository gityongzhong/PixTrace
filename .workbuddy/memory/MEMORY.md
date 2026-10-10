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

### 当前进度（2026-10-10 更新）

- **v0.5.0 主题对齐流晷计时器（当前基准，用户审美锚点）**：用户发来上一款产品
  「流晷计时器」截图并确认全面对齐。**重新解读 v0.3.9 的「太突兀」**：病灶不是对比度高，
  而是底色不够深导致靠「边框+高光+阴影」三件套撑层次；把蓝压灰治标不治本。
  现行风格：窗底 #0f1013 近黑、面板 #17181c 无边框纯明度差、强调色 #1f7fff 只用在焦点
  （选中行/主按钮/单选点/链接）、列表选中=实心亮蓝块白字、按钮/列表/菜单全去边框、
  输入框 border transparent 占位+focus 亮蓝描边、圆角 8/10。
  **凡涉及界面审美，以流晷计时器为准：近黑底、无边框、亮蓝焦点、装饰克制。**
- **v0.4.0 三处动画**：新增 app/ui/anim.py（TintAnimation/ValueRoller/mix/paint_tint_frame）。
  QSS 不支持 CSS 动画（transition/keyframes 都没有），过渡只能用 Qt 动画框架算中间值。
  三规矩写死：不逐帧改 QSS（每帧全量重算掉帧）、**graphics effect 禁止嵌套（含父子）**、
  动画 150-220ms 且只在状态变化瞬间播。进度条 ValueRoller（完成必须 snap 停表）、
  拖拽框 TintAnimation+paintEvent 自绘
  （**自绘控件不要调 super().paintEvent()**，否则 QSS 背景叠加）。
  QRect.adjusted 只吃 int，内缩半像素必须 QRectF。shot_gui settle() 等动画跑完再截。
- **v0.5.1 重叠修复（v0.4.0 的坑爆了）**：状态 QLabel 挂透明度 effect + 所在面板挂投影
  = 嵌套 effect，真实上屏文字叠影（fade_in 已删）。**widget.grab() 截图照不出
  嵌套 effect 叠影**——grab 与上屏合成路径不同，涉及 effect 的改动不能只靠截图验收。
  状态文字现在：完整文案存 _status_full + 按宽度 elide（resizeEvent 重算）+ tooltip 全文；
  动作行布局 = 状态(弹性宽) + 进度条贴 取消/开始处理。
- **v0.4.1 移除工具条「设置」菜单**：界面入口只剩 添加图片/添加文件夹/清空列表。
  模型管理 = Ctrl+M 或 start() 兜底弹窗；show_about()/open_model_dir() 无 UI 触发待挂载。
- **v0.3.7 质感改造（已被 v0.5.0 取代，但 effects.py 沿用）**：app/ui/effects.py
  QGraphicsDropShadowEffect 卡片级 radius10（会被父级裁剪）、弹出层 radius22（QMenu）。
  QSS 坑仍在注释里：QPushButton 全局 focus 蓝框会常亮（删）；
  ::item:selected 加 border-left 会让列间竖线（删）。
- **项目已 git init**（基线 21a65b1 = v0.3.6；v0.5.0 = 8eaabdc）。.gitignore 排除
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
