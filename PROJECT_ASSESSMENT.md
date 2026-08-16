# ImagePorter（鲸舟）全面分析评估报告

**评估日期**: 2026-08-17 · **评估基线**: `main` 分支 @ `7078e58` + 未提交重构（`imageporter/` 包、`tests/`、CI）
**项目类型**: Flet (Flutter) 桌面 GUI 应用 · Docker CLI 包装工具 · MIT 开源单人项目
**代码规模**: 生产代码约 1,790 行（main.py 1,081 + 包模块 709），测试 362 行

---

## 一、执行摘要

ImagePorter 定位清晰——解决**离线环境 Docker 镜像分发**这一真实工程痛点，产品判断优秀。本轮未提交的重构是实质性进步：上一份审核报告（CODE_REVIEW_REPORT.md）指出的「单文件 God Object」已拆出可测试的 `core`/`ui`/`utils` 分层，并配套了 53 个全部通过的单元测试和三平台 CI 矩阵。

但存在一个**必须立即修复的致命回归**：重构在 `main.py:800` 留下了对 `_env_cache` 的悬空引用——该符号未随其他函数一起导入，**每次点击「开始执行」都会以 `NameError` 失败**（被外层 `except Exception` 吞掉后以「执行异常」提示）。核心功能实际处于不可用状态，且 CI 的 `py_compile` 无法发现此类运行时错误——这正是缺少编排层测试的代价。

### 总体评分

| 维度 | 得分 | 简评 |
|---|---|---|
| 架构与模块化 | 6.5 / 10 | 方向正确，`main()` 仍是 ~1,040 行巨函数 |
| 正确性与可靠性 | **4 / 10** | 1 个致命回归 + 并发边界缺陷 |
| 代码质量 | 6 / 10 | 核心模块干净；残留死代码、重复逻辑、静默异常 |
| 测试保障 | 5 / 10 | 53 个好测试，但覆盖面约达标准的 1/3 |
| CI/工程化 | 5.5 / 10 | 三平台矩阵是亮点；缺 lint/类型/覆盖率/打包元数据 |
| 安全性 | 8 / 10 | 列表参数执行、正则校验，无注入面 |
| 跨平台兼容 | 7 / 10 | PTY 降级方案修复了旧致命问题 |
| UI/UX | 7.5 / 10 | 单人项目而言相当精致 |
| 文档与开源治理 | 6.5 / 10 | README/BUILD_GUIDE 优秀；AGENTS.md 已过时 |
| **综合** | **6 / 10** | 修复 P0 后可达 7+ |

---

## 二、上一轮审核整改追踪

| 旧报告问题 | 状态 | 证据 |
|---|---|---|
| 单文件 God Object（1,418 行） | **部分修复** | main.py 降至 1,081 行，拆出 5 个模块；但 `main()` 闭包仍 ~1,040 行 |
| Windows `pty` 导入崩溃 | **已修复** | `docker.py:14-19` 条件导入 + PIPE 降级 |
| `get_image_platforms` 返回值不匹配崩溃 | **已修复** | `docker.py:263-279` 统一返回 `tuple[list, str]`，有测试覆盖 |
| 无任何测试 | **大幅改善** | 53 个测试，parser/docker(mock)/constants 全绿（0.03s） |
| 无 CI | **已建立** | 3 OS × 3 Python 矩阵 |
| 线程竞态 / 裸 except 吞异常 | **部分改善** | UI 单写者模式 + `stats_lock` 到位；静默 `except` 仍有 ~15 处 |
| 魔法数字 | **已修复** | `constants.py` 集中管理且有守护测试 |
| 无 i18n / 响应式布局 | 未处理 | 面向中文用户可接受，暂不阻塞 |

---

## 三、问题清单（按严重度分级）

### 🔴 CRITICAL（合并前必须修复）

**C-1 · `_env_cache` 未定义，启动任务必崩**
`main.py:800`：`if _env_cache["docker_ok"] is not True:` —— 导入列表（`main.py:28-32`）中没有 `_env_cache`。任何有效输入点「开始执行」后，`run_worker` 在此抛 `NameError`，被 `main.py:900-902` 捕获，用户只看到「执行异常： name '_env_cache' is not defined」。
**修复**：该行本属冗余——`check_docker_available()`（`docker.py:79-91`）内部已做缓存判断，直接调用即可，删除对私有缓存的越层访问（同时也修复了层间泄漏：UI 层不应触碰 core 模块的私有符号）。

### 🟠 HIGH

**H-1 · 同名镜像并发竞态，可能导出错误架构**
`dedup_keep_order`（`parser.py:28`）只做**字符串级**去重。输入 `nginx` 与 `nginx:latest`（或 `docker.io/library/nginx`）是两个不同字符串、同一实际镜像 → 两个线程并发对同一 tag 做 `pull --platform` / `save`（`main.py:706-789` 顺序仅保证单任务内多平台串行），`docker save` 按 tag 导出，tar 内容取决于竞态时的本地 tag 指向——**可能拿到错误架构的镜像**，且这是离线部署工具，错误会在目标机器上才暴露。
**修复**：规划阶段将镜像名规范化（补全默认 registry/tag）后按规范化身份去重或串行化。

**H-2 · `check_docker_available` 只探测二进制，不探测守护进程**
`docker.py:79-91` 仅验证 docker 可执行文件存在。Docker Desktop「已安装未启动」时校验通过，直到第一个 `pull` 才失败，且报错深埋在任务日志里——与错误消息中「已启动」的承诺（`docker.py:87`）不符。
**修复**：以短超时执行 `docker info` 作为真实健康检查（可复用 `get_host_platform` 顺带完成）。

**H-3 · 失败路径的清理可能删除用户既有镜像**
`main.py:787-788`：只要 `cleanup_switch` 开启就执行 `docker rmi`，**不区分本次 pull 是否成功**。若 pull 失败但本地存在同名旧镜像（用户自己拉的），会被误删——接近数据丢失行为。
**修复**：仅当 `pull_ok` 为真才执行 `docker_remove`。

**H-4 · 测试覆盖远低于 80% 标准，且恰好放走了 C-1**
main.py（占生产代码 ~60%）编排逻辑零测试；`_run_pty_docker`/`_run_pipe_docker`/`utils/config.py`/`ui/task_row.py` 零测试；CI 无覆盖率步骤，本地连 `pytest-cov` 都未安装。C-1 这类 bug 正是 `run_worker` 冒烟测试（mock docker 函数、断言不抛异常）能拦下的。

### 🟡 MEDIUM

| # | 问题 | 位置 |
|---|---|---|
| M-1 | `main()` 单函数 ~1,040 行，超 800 行文件红线与 50 行函数红线的 20 倍；对话框、侧边栏、事件泵、worker 全部闭包耦合 | `main.py:42-1081` |
| M-2 | Tab 切换逻辑两处重复实现（事件处理器直改 vs `_set_tab_visible`） | `main.py:502-530` vs `546-553` |
| M-3 | 死代码：`_ThrottledUpdater`（47 行，自述「currently unused」）、`TaskRow` 的 `ui`/`_page` 参数、`PLATFORM_CACHE_FILE` 常量、`log_cb` 参数 ×2 | `task_row.py:16-47`、`constants.py:24`、`docker.py:263,282` |
| M-4 | 静默吞异常 ~15 处；`save_theme_mode` 失败无任何反馈，用户不知主题未持久化 | `config.py:41-42`、`main.py:700-703` 等 |
| M-5 | `get_host_platform` 失败时缓存默认值 `linux/amd64` 且永不过期——ARM 机器上 docker 短暂无响应会导致整会话平台判断错误 | `docker.py:251-260` |
| M-6 | manifest 的 `unknown/unknown`（attestation 产物）通过过滤器污染平台列表 | `docker.py:273-276` |
| M-7 | 无 `pyproject.toml`：版本三处不一致（`__init__.py` 1.1.0 / 关于对话框硬编码 v1.0.0 / README 徽章写 flet-latest 实则锁 0.81.0）、无 dev 依赖声明、无工具链配置 | 全局 |
| M-8 | `AGENTS.md` 过时：引用已删除的 `test.py`、声称「尚无正式测试套件」 | `AGENTS.md` |

### 🟢 LOW

- `os.access(W_OK)` 在 Windows 上语义不可靠（`main.py:820`），实际写入失败已有兜底；
- digest 引用生成含 `@` 的文件名（`docker.py:304-311`），合法但观感差；
- 架构胶囊选中态双重初始化（构造时样式 + `refresh_arch_chip_styles()` 重刷），`#E6F0FF`/`#1E3A5F` 硬编码双主题色未入令牌表（`main.py:276-320`）；
- 测试用 unittest 类风格，可迁移 pytest 惯例与 `pytest.mark` 分层标记。

---

## 四、分维度详细评估

### 4.1 架构：从「God Object」到分层的一半路程

新结构 `core`（无 Flet 依赖，纯逻辑）/ `ui` / `utils` / `constants` 是教科书式的正确切分——**core 不依赖 UI** 这一依赖方向纪律执行得很干净，直接换来 parser/docker 的可测性（53 个测试 0.03 秒跑完证明了这一点）。

但对照旧报告建议的完整蓝图与业界惯例（Flet 官方示例亦推荐按 view/component/service 分文件）：`main.py` 目前完成的是「搬走常量与纯函数」，**状态管理仍在 `main()` 闭包中**（`running`、`task_stats`、`task_rows`、`ui_events` 等十余个闭包变量互相交织）。下一阶段应拆出 `dialogs.py`（两个 AlertDialog ~90 行）、`worker.py`（`run_worker`/`process_image` ~190 行，与 Flet 完全解耦后可测）、`pump.py`（`ui_pump` 事件循环）。其中 **worker 解耦是解锁 80% 覆盖率的前提**。

### 4.2 并发设计：本轮重构的最大亮点

值得肯定的模式（多数 Flet 项目做错了，这里做对了）：

- **单写者 UI**：工作线程只 `emit()` 入队（`main.py:543-544`），唯一的 `ui_pump` 协程批量消费（`EVENT_BATCH_LIMIT=500`/`50ms`）并统一 `page.update()`——规避了 Flet 多线程刷控件的经典崩溃源；
- **统计一致性**：`task_stats` 全程持 `stats_lock` 读写（`main.py:581-587`）；
- **停止语义完整**：`stop_event` 一路穿透到子进程运行器，`terminate → wait(1s) → kill` 升级（`docker.py:148-162`），中止时清理残缺 tar（`main.py:774-778`）；
- **任务内多平台串行**（`process_image` 的 for 循环）避免了同 tag 自竞争——但跨任务同名问题见 H-1。

一个客观局限：杀掉 docker CLI 并不会停止 daemon 侧的层下载（Docker 架构使然），README「界面状态与后台 Docker 子进程保持一致」的表述对 CLI 进程成立、对 daemon 下载不完全成立，建议文档措辞收敛。

### 4.3 测试与质量门禁

**优点**：`test_docker.py` 的 mock 边界划得专业（只 mock `subprocess.run`/`_resolve_docker_path`，纯函数全真跑）；`test_constants.py` 用守护测试锁住配置一致性（标签/对照表覆盖所有平台选项）是好实践。

**缺口**（对照 80% 覆盖率 + TDD 强制标准）：按生产 LOC 估算当前实际覆盖约 25-35%；CI 只有 `py_compile` + pytest，无 `--cov` 门槛、无 ruff、无 mypy；`requirements.txt` 不含 dev 依赖（CI 里临时 `pip install pytest`，`pip-audit`/`pytest-cov` 缺位）。C-1 的逃逸是流程问题的具象化：**py_compile 只验语法不验名字解析**。

### 4.4 安全性

- ✅ 所有 subprocess 均列表参数、无 `shell=True`，镜像名先经正则校验（`parser.py:10-15`）再用——无命令注入面；
- ✅ 无密钥、无遥测；`prefs.json` 仅存主题偏好；
- ⚠️ 唯一提一句：`_build_exec_env` 全量复制 `os.environ` 传给子进程属常规做法，但若未来引入私有 registry 凭证传递，需注意 `docker manifest inspect` 对私有仓的认证走 `~/.docker/config.json`，错误信息可能含仓库名——当前处理（返回「Manifest不可用」）已足够收敛。

### 4.5 跨平台

PTY 条件导入 + Windows PIPE 降级（`docker.py:14-19, 240-248`）修复了旧致命问题；Docker 路径提示表覆盖 Homebrew/Docker Desktop 双平台安装位（`constants.py:28-37`）。Windows 上 `docker pull` 非 TTY 时输出为纯行文本，README 宣传的「层级进度条」在 Windows 降级为逐行日志——建议 README 明示。`explorer /select,` 用法正确。

### 4.6 UI/UX

对一个单人开源工具而言完成度很高：空状态引导、架构对照表弹窗（解决「arm64/v8 到底选哪个」这一真实用户困惑，产品洞察好）、主题记忆、终端风日志、悬停高亮+点击定位文件。对比度注释（`#E2E8F0 → #CBD5E1`，`main.py:65-66`）显示有无障碍意识。改进空间：架构胶囊选中态依赖 `ctr.data` 布尔复用（语义含糊，宜用专门字段）；中止后按钮禁用态到恢复的路径依赖 `RUNNING` 事件，若 worker 异常早退有 `finally` 兜底（`main.py:904`）——这条链路是闭环的，好。

### 4.7 文档与开源治理

README 准确（含 `venv` 避坑说明）、BUILD_GUIDE 详尽实用。缺口：README 邀请 PR 但无 CONTRIBUTING；无 CHANGELOG（版本已到 1.1.0 却无记录）；AGENTS.md 与现状脱节（M-8）；无 issue 模板。均不阻塞，但按开源项目成熟度模型（含 README→LICENSE→CI→CONTRIBUTING→CHANGELOG 的递进）处于中段。

---

## 五、优先级改进路线图

**P0 — 立即（当前代码不可发布）**
1. 修复 C-1：`main.py:800` 改调 `check_docker_available()`；
2. 修复 H-3：`docker_remove` 前置 `pull_ok` 条件；
3. 补 `run_worker` 冒烟测试（mock docker 层，验证启动→规划→执行→收尾全链不抛异常）——这个测试会直接抓住 C-1。

**P1 — 近期（1-2 个迭代）**
4. H-1 镜像身份规范化去重/串行化；H-2 守护进程健康检查；
5. 引入 `pyproject.toml`（版本单一来源 + `[project.optional-dependencies] dev` + ruff/pytest 配置），CI 增加 `ruff check`、`pytest --cov --fail-under`、mypy（core 模块先行）；
6. 抽离 `worker.py`（纯逻辑、无 Flet），将编排逻辑纳入测试，目标 core+worker 覆盖 ≥80%；
7. 更新 AGENTS.md、关于对话框版本号、README flet 徽章。

**P2 — 中期**
8. 继续拆分 `main.py`（dialogs/sidebar/pump，目标单文件 <400 行）；
9. 清理 M-3 死代码；`save_theme_mode` 等静默异常加最小反馈；`get_host_platform` 失败不缓存；
10. CONTRIBUTING + CHANGELOG + issue 模板；评估 i18n（gettext 抽串）若目标受众扩展。

---

## 六、结论

这是一次**方向完全正确、执行还差最后一公里**的重构：分层纪律、并发模式、测试起步都达到了小型桌面工具的良好水准，三平台 CI 甚至超过多数同类开源项目。但 C-1 这类「重构缝合处的悬空引用」提醒：**在编排层无测试覆盖的情况下，重构后的第一件事应该是跑通端到端主路径**——目前它没有跑通。修复 P0 三项（预计 <1 小时工作量）后，项目即可回到可发布状态，并具备向 7-8 分演进的全部基础。
