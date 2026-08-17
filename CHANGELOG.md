# Changelog

本项目的显著变更记录。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [1.5.0] - 2026-08-17

### Changed

- **升级 flet 0.81.0 → 0.86.5（黑屏根治）**：修复 macOS 打包版在
  多显示器/混合 DPI（Retina + 外接 1080p）环境下窗口位于外接屏时
  渲染失败（整窗黑、无报错、移回主屏亦不恢复）的上游缺陷；同时修复
  打包版 `page.window` 尺寸/最大化/居中 API 不生效的问题（窗口尺寸
  与最大化记忆功能自此真正可用）。API 兼容性经 234 项测试零修改验证。

## [1.4.2] - 2026-08-17

### Fixed

- **多显示器环境打包版黑屏（真正根因）**：macOS 桌面渲染引擎在窗口位于
  副显示器时渲染失败（部分/整窗黑，无任何报错；移回主屏可恢复）。此前
  「最大化时跳过居中」恰好放弃了把窗口拉回主屏的机会。修复：
  - 启动时**无条件居中**窗口，摆脱系统记忆的副屏旧位置
  - 窗口移动/缩放事件触发**主动整页重绘**，跨屏拖动后自愈
- **打包版 Info.plist 版本号恒为 1.0.0**：flet build 不支持 pyproject 的
  dynamic 版本读取，改为静态声明（发布时与 `__version__` 同步）。
- 已知问题（待后续）：打包版启动时 `page.window` 尺寸/最大化设置不生效，
  窗口为引擎默认尺寸（居中显示，功能不受影响）。

## [1.4.1] - 2026-08-17

### Fixed

- **桌面端（打包版）启动黑屏（初判，未除根）**：最大化状态下不再同时下达
  `width/height` 与 `center()` 等相互矛盾的窗口指令；窗口事件持久化延迟到
  UI 挂载完成后，最大化时保存还原尺寸而非全屏尺寸。

## [1.4.0] - 2026-08-17

### Fixed

- **侧边栏内容遮挡**：侧栏上部区域启用滚动（`scroll=AUTO`，修复环境卡片被
  截断、「开始执行」按钮被叠压的问题——注释本就声明"上部可滚动"，系实现笔误）。
- **窗口默认最大化**：首次运行以最大化打开；记忆最大化状态与上次窗口尺寸
  （写入 prefs.json，与主题偏好共存，窗口事件节流落盘，尺寸下限 600×400）。

### Changed

- **布局优化**：环境状态由侧边栏卡片迁移为**窗口底部横向状态栏**
  （系统摘要 | Docker 三态 | 版本·引擎 | 操作入口 | 刷新），侧边栏彻底减负；
  侧边栏头部改为纯锚点图标（tooltip 显示全名），消除与原生窗口标题的品牌重复。

### Added

- **压缩导出**：默认以流式 gzip 将 `docker save` 输出直接压缩为 `.tar.gz`
  （等价 `docker save | gzip`，峰值磁盘占用仅为最终压缩文件，无中间 tar）；
  目标机 `docker load -i` 可直接加载。导出设置新增「压缩导出」开关（默认开启，
  关闭则保持未压缩 `.tar`）；成功日志与历史记录展示压缩后体积，日志附原始体积
  与节省比例（实测 busybox 节省 57%）。中止时自动清理残缺 `.tar.gz`。

## [1.3.0] - 2026-08-17

### Added

- **导出历史**：成功导出自动落档至 `~/.imageporter/history.json`（上限 200 条，
  新记录在前，重启保留）；新增「导出历史」Tab——含时间/镜像·架构/tar 文件名/
  体积/文件是否仍在磁盘，支持在文件管理器中定位、单条删除记录与一键清空
  （清空需二次确认，均不影响已导出的 tar 文件）。
- **本机镜像管理**：新增「本机镜像」Tab——展示本机已下载镜像（名称、创建时间、
  体积，悬空镜像显示短 ID），支持名称搜索过滤、勾选批量删除与单个删除；
  所有删除操作均弹出确认对话框（列明数量与不可恢复警告）后后台执行 `docker rmi`，
  结果以日志与 SnackBar 回报并自动刷新列表。
- 右侧面板由双 Tab 重构为四 Tab（任务列表/运行日志/导出历史/本机镜像）；
  「在文件管理器中显示」提取为跨平台共用工具。
- 新增 tag 触发的 Release 流水线：自动构建 macOS `.app` 与 Windows 安装包
  并附到对应 GitHub Release。

### Changed

- **环境感知**：侧边栏新增「环境状态」卡片——展示系统版本/架构与 Docker
  安装状态、守护进程运行状态（🟢/🔴/⚪ 三态指示）、服务端版本和主机平台，
  支持手动刷新；应用启动与每次任务结束后自动后台探测（不阻塞 UI）。
- **一键修复入口**：Docker 未运行时卡片提供「启动 Docker Desktop」按钮
  （macOS/Windows，点击后进入等待态）；未安装或无启动器平台提供官方
  下载/文档链接。
- **自动重试**：Docker 不可用时每 10 秒后台重探，守护进程恢复后卡片
  自动变绿，无需手动刷新。
- **环境自检命令**：`python main.py --check-env` 输出系统与 Docker 环境
  报告，用于安装与运行排障。

### Changed

- **架构命名归一**：系统行与 Docker 引擎行统一使用 Docker Hub 词汇
  （`aarch64`→`arm64`、`x86_64`/`AMD64`→`amd64`、`i386/i686`→`386`），
  消除"系统 arm64 vs 引擎 aarch64"的展示混淆；版本明细行标签改为
  「引擎」并附悬停说明（Docker Desktop 守护进程运行于 Linux 虚拟机，
  容器均为 Linux 环境，架构与系统行为同一 CPU）。
- main.py 继续拆分（794 → 314 行）：明暗主题、左侧边栏、右侧面板分别外移至
  `ui/theme.py`、`ui/sidebar.py`（`SidebarControls` 控件束）、`ui/panels.py`
  （`MainPanels`）；Tab 切换与空状态刷新逻辑随面板内聚，行为保持等价。
- 字符串字面量样式值统一为枚举（`FontWeight.BOLD` / `AnimationCurve.EASE_OUT`），
  UI 刷新统一采用尽力而为的防御性包裹。

### Added

- 新增 theme/sidebar/panels 三个模块的无窗口构建测试，测试总数 125 → 146，
  imageporter 包覆盖率维持 ~89%。

## [1.2.0] - 2026-08-17

### Fixed

- **致命**：修复点击「开始执行」必然触发 `NameError` 的回归（UI 层对 core 私有缓存
  `_env_cache` 的悬空引用），核心流程恢复可用。
- **致命**：修复 PTY 模式下所有 Docker 输出行被静默丢弃的问题（CRLF 行尾
  `\r` 处理错误），「实时日志与层级进度」特性首次真正生效。
- 修复 flet 0.81 API 漂移导致的三处静默失效：SnackBar 提示（`page.snack_bar`
  已移除）、路径悬停下划线（`Text.decoration` 已移除）、任务行图标更新
  （`Icon.name` 已更名 `icon`——此前会导致事件泵崩溃）。
- 自动清理不再删除本轮拉取失败（可能是用户既有的）同名本地镜像。
- 修复 `nginx` 与 `nginx:latest` 等等价写法并发执行导致的同 tag 竞态
  （可能导出错误架构的镜像），规划期按规范化身份去重。
- Windows PIPE 降级路径的中止检测不再被 `readline` 阻塞：静默进程
  （如长时间无输出的 `docker save`）现可被及时中止。

### Changed

- Docker 可用性检查升级为真实守护进程探测（`docker info`），并区分
  「未安装」与「守护进程未运行」；失败不缓存，启动 Docker 后自动自愈。
- 主机平台探测失败不再缓存错误的 amd64 默认值。
- manifest 中 `unknown/unknown`（attestation 产物）不再计入可用架构。
- 状态横幅卡片（status_banner）此前构建后从未挂载，现已按原设计意图接入布局。
- Tab 切换逻辑统一为单一入口，消除重复实现。

### Added

- 新增 `imageporter.core.engine`：UI 无关的任务编排引擎（emit 回调注入），
  `main.py` 降至 800 行以内（1,081 → 794）。
- 新增 `imageporter.ui.dialogs`：关于/架构对照对话框外移，版本号改用
  `__version__` 单一来源。
- 新增 `pyproject.toml`：版本单一来源、`dev` 可选依赖、ruff/mypy/pytest/
  coverage 工具链配置。
- CI 拆分为 lint（ruff）/ type-check（mypy）/ test（3 OS × 3 Python）三类
  job，测试增加覆盖率门禁（imageporter 包 ≥ 80%）。
- 测试套件从 53 项扩充至 125 项（编排引擎/任务行/对话框/配置/PTY-PIPE
  运行器/镜像身份规范化），imageporter 包覆盖率约 89%。
- 新增 CONTRIBUTING.md、issue 模板（bug/feature）。

### Removed

- 清理死代码：`_ThrottledUpdater`（47 行未用类）、未使用的
  `PLATFORM_CACHE_FILE` 常量、`get_image_platforms`/`choose_platforms` 的
  `log_cb` 参数、`TaskRow` 未用的 `ui`/`page` 参数。

## [1.1.0] - 2026-08

- 模块化重构第一阶段：拆分 `constants` / `core(parser, docker)` / `ui(task_row)` /
  `utils(config)`；引入 53 项单元测试与三平台 CI 矩阵。

## [1.0.0] - 2026

- 首个版本：Flet UI、多架构并发拉取导出、PTY 进度捕获、主题记忆、偏好设置。

[1.5.0]: https://github.com/xuefei0722/ImagePorter/releases/tag/v1.5.0
[1.4.2]: https://github.com/xuefei0722/ImagePorter/releases/tag/v1.4.2
[1.4.1]: https://github.com/xuefei0722/ImagePorter/releases/tag/v1.4.1
[1.4.0]: https://github.com/xuefei0722/ImagePorter/releases/tag/v1.4.0
[1.3.0]: https://github.com/xuefei0722/ImagePorter/releases/tag/v1.3.0
[1.2.0]: https://github.com/xuefei0722/ImagePorter/releases/tag/v1.2.0
