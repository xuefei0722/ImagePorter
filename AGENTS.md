# Repository Guidelines

## Project Structure & Module Organization

- `main.py`: Flet 应用入口 —— 仅负责 UI 组装、事件泵（`ui_pump`）与引擎适配层，业务编排在 engine 中完成。
- `imageporter/`: 核心包
  - `constants.py` — 全局常量与设计令牌（窗口/并发上限/Docker 路径提示/平台架构表）
  - `core/parser.py` — 镜像名解析、校验与规范化身份去重
  - `core/docker.py` — Docker CLI 交互（pull/save/rmi/manifest/守护进程探测，PTY + PIPE 双路径）
  - `core/engine.py` — 任务规划与并发执行引擎（UI 无关，emit 回调注入事件）
  - `ui/task_row.py` — TaskRow 任务行组件（状态迁移，刷新统一由事件泵批处理）
  - `ui/dialogs.py` — 关于/架构对照表对话框
  - `utils/config.py` — 用户偏好持久化（主题等）
- `tests/`: pytest 测试套件（全部 mock Docker 交互，无需真实 daemon 或窗口）
- `docs/BUILD_GUIDE.md`: 原生应用打包指南（macOS）
- `assets/`: 静态资源（应用图标）；`build/`、`dist/`、`*.app`、`*.exe` 为生成产物，勿提交。

## Build, Test, and Development Commands

```bash
# 环境准备
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # 运行时 + 开发工具链（pytest/ruff/mypy 等）

# 运行应用
flet run main.py

# 测试（覆盖率门禁 80%，针对 imageporter 包）
python -m pytest tests/ -v --cov=imageporter --cov-fail-under=80

# 静态检查（与 CI 门禁一致）
ruff check .
mypy
```

## Coding Style & Naming Conventions

- PEP 8，函数签名带类型注解；`ruff`（line-length 120，含 isort/pyupgrade/bugbear 规则）与 `mypy` 为强制门禁。
- `snake_case` 函数/变量，`PascalCase` 类，UI 组件控件属性用 `xxx_ctrl` 后缀区分。
- 依赖方向纪律：`core/` 不得 import flet；新增业务逻辑优先落在 `core/` 并配套测试。
- 所有 subprocess 调用必须使用列表参数（禁止 `shell=True`）；镜像名一律先经 `parser` 校验。
- UI 线程模型：工作线程只允许 `emit()` 入队，控件刷新只发生在 `ui_pump` 单写者循环。

## Testing Guidelines

- 修改 `core/engine.py`、`core/docker.py`、`core/parser.py`、`utils/config.py`、`ui/` 时必须同步更新/新增测试。
- Docker 交互一律 mock（参考 `tests/test_engine.py` 的 `PatchedDockerTestCase` 基类与记录型 `Recorder` emit）。
- PTY/PIPE 运行器允许使用 `sys.executable` 起真实短命子进程做集成级断言（跨平台安全）。
- Flet 控件可在无窗口环境直接实例化并断言状态迁移（参考 `tests/test_task_row.py`）。
- 提交前本地跑通三大门禁：`pytest --cov`、`ruff check .`、`mypy`。
