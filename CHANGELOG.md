# Changelog

本项目的显著变更记录。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Changed

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

[1.2.0]: https://github.com/xuefei0722/ImagePorter/releases/tag/v1.2.0
