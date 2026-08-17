# 整改进度追踪（FIX_TRACKING）

**基线报告**: [PROJECT_ASSESSMENT.md](./PROJECT_ASSESSMENT.md)（2026-08-17 评估）
**整改完成时间**: 2026-08-17 · **版本**: v1.2.0
**状态图例**: ✅ 已完成并验证 · ⏸ 部分完成 · ⏭ 暂缓（含理由）· ➕ 修复过程中新发现

---

## 一、最终校验结果（三大门禁 + 编译）

| 门禁 | 命令 | 结果 |
|---|---|---|
| 单元测试 + 覆盖率 | `pytest tests/ --cov=imageporter --cov-fail-under=80` | ✅ **125 passed**（基线 53），覆盖率 **88.97%** ≥ 80% |
| 静态检查 | `ruff check .` | ✅ All checks passed（33 项违规清零） |
| 类型检查 | `mypy`（imageporter 全包） | ✅ 11 个源文件无问题（基线 0 检查） |
| 语法/导入 | `py_compile` 全模块 + `import main` | ✅ 通过 |

**代码体量变化**: main.py 1,081 → **794 行**（低于 800 红线）；新增 `core/engine.py`(320)、`ui/dialogs.py`(127)；测试 362 → 1,081 行（6 个测试文件）。

---

## 二、报告问题清单逐项状态

### CRITICAL

| 编号 | 问题 | 状态 | 证据 |
|---|---|---|---|
| C-1 | `_env_cache` 悬空引用，点「开始执行」必崩 NameError | ✅ | 编排逻辑迁入 `engine.py`，直接调用 `check_docker_available()`；回归测试 `test_unexpected_name_error_surfaced_not_crash` 永久防护此类缺陷 |

### HIGH

| 编号 | 问题 | 状态 | 证据 |
|---|---|---|---|
| H-1 | 同名镜像（`nginx` ≡ `nginx:latest`）并发竞态 | ✅ | `parser.normalize_image_identity` 规范化去重（含 `library/`、`docker.io/` 前缀等价）；测试 `test_equivalent_spellings_deduped` 等 3 项 + parser 8 项 |
| H-2 | 只探测二进制不探测守护进程 | ✅ | `check_docker_available` 追加 `docker info` 探测（`DAEMON_PROBE_TIMEOUT=8s`），区分「未安装/未运行」，失败不缓存自愈；测试 5 项 |
| H-3 | 失败路径 cleanup 可能误删用户镜像 | ✅ | `engine.py`：`if self.config.cleanup and pull_ok`；测试 `test_no_rmi_when_pull_failed` |
| H-4 | 覆盖率远低于 80%，编排层零测试 | ✅ | imageporter 包覆盖率 **89%**；新增编排冒烟/校验/去重/清理/停止/回归防护共 23 项；CI 增加 `--cov-fail-under=80` 门禁 |

### MEDIUM

| 编号 | 问题 | 状态 | 证据 |
|---|---|---|---|
| M-1 | `main()` 巨函数（~1,040 行） | ⏸→✅ | engine(320 行)/dialogs(127 行) 外移，main.py 794 行；状态管理收拢为 `RunEngine` 内聚（`RunStats` + 锁）。报告的 400 行进阶目标未追（侧边栏/事件泵仍为闭包，见「暂缓项」） |
| M-2 | Tab 切换逻辑两处重复 | ✅ | 统一 `_switch_tab(show_log, e)`（main.py:439） |
| M-3 | 死代码（_ThrottledUpdater 等） | ✅ | grep 确认 `_ThrottledUpdater`/`PLATFORM_CACHE_FILE`/`log_cb` 全部清除；TaskRow 签名精简为 `(image, platform)` |
| M-4 | 静默吞异常、保存无反馈 | ✅（关键路径） | `save_theme_mode` 返回 bool + `toggle_theme` 记录 `[警告]` 日志（main.py:99-100）；测试 `test_save_failure_returns_false`。剩余 UI 兜底 except 保留（刷新尽力而为语义，已注释） |
| M-5 | `get_host_platform` 失败缓存错误默认值 | ✅ | 失败不缓存、下次自动重试；测试 `test_failure_returns_default_without_caching` |
| M-6 | `unknown/unknown` 污染架构列表 | ✅ | `get_image_platforms` 过滤；测试 `test_unknown_attestation_platforms_filtered` |
| M-7 | 无 pyproject.toml、版本三处不一致 | ✅ | pyproject.toml（dynamic version ← `__version__` 单一来源）+ dev 依赖 + 工具链配置；关于对话框动态读 `__version__`（测试 `test_version_single_source`）；README 徽章改 flet-0.81.0 |
| M-8 | AGENTS.md 过时 | ✅ | 全文重写（新模块结构、三大门禁命令、线程模型约定） |

### LOW

| 问题 | 状态 | 说明 |
|---|---|---|
| `os.access(W_OK)` Windows 语义不可靠 | ⏭ | 实际写入失败已有兜底（save 失败路径删除残缺 tar + 状态回报）；更换探测方案收益低 |
| digest 文件名含 `@` | ⏭ | 各平台文件系统均合法，仅观感问题 |
| 架构胶囊双重初始化/硬编码双主题色 | ⏭ | 无行为缺陷；随未来设计令牌化一并处理 |
| unittest → pytest 风格迁移 | ⏭ | unittest 类风格与 pytest 运行器完全兼容，现有 125 项均由 pytest 驱动 |

---

## 三、➕ 修复过程中新发现并已修复的缺陷（原报告未捕获）

| 严重度 | 发现 | 修复与防护 |
|---|---|---|
| **CRITICAL** | **PTY 输出行全部被丢弃**：`raw.split("\r")[-1]` 对 CRLF 行尾取到空串，「实时日志与层级进度」核心特性自始未生效（`docker.py _flush`） | 保留最后一段**非空**内容；测试 `test_completes_and_captures_output`、`test_carriage_return_progress_keeps_last_segment` |
| **CRITICAL** | **`Icon.name` 已不存在于 flet 0.81**（应为 `.icon`）：首个任务事件即令事件泵崩溃——此前被 C-1 的更早异常完全掩盖 | 全部改用 `.icon`；`test_task_row.py` 12 项状态迁移测试防护 |
| **HIGH** | **SnackBar 全部不显示**：`page.snack_bar` 属性已从 flet 0.81 移除（应用所有用户提示静默失败） | 统一改 overlay + `open=True` 模式（事件泵 SNACKBAR 处理器、dialogs 错误回退）；测试 `test_open_failure_shows_snackbar_via_overlay` |
| MEDIUM | 悬停下划线失效（`Text.decoration` 已移除，应走 `TextStyle`）；`Container.cursor` 属性不存在 | `style=ft.TextStyle(decoration=...)`；移除 cursor 死赋值；测试覆盖 |
| MEDIUM | Windows PIPE 路径停止被 `readline` 阻塞：静默进程（长时间 `docker save`）无法及时中止 | 读线程 + 队列轮询重构；测试 `TestRunPipeDocker::test_stop_event_terminates`（静默子进程 30s sleep 秒级中止） |
| LOW | `status_banner` 构建后从未挂载（死 UI 代码，作者注释表明本意是替换顶部布局） | 按注释意图接入 `main_content`（⚠️ 唯一未经真实 GUI 目视验证的变更，建议 `flet run main.py` 确认视觉） |
| LOW | `choose_platforms` 函数体残留 `log_cb` 引用（M-3 清参数时的连带） | 修正；全测试通过 |

---

## 四、路线图执行状态

| 优先级 | 项 | 状态 |
|---|---|---|
| P0-1 | 修复 C-1 | ✅ |
| P0-2 | 修复 H-3 | ✅ |
| P0-3 | run_worker 冒烟测试 | ✅（升级为 23 项编排引擎套件） |
| P1-4 | H-1 身份去重 / H-2 守护进程检查 | ✅ |
| P1-5 | pyproject + CI 三门禁 | ✅ |
| P1-6 | 抽离 worker（engine.py）纳入测试，core 覆盖 ≥80% | ✅（引擎 95%，全包 89%） |
| P1-7 | AGENTS.md / 版本号 / README 徽章 | ✅ |
| P2-8 | 拆分 dialogs（main.py <800） | ✅（794 行）；sidebar/pump 进一步拆分 ⏭（无 GUI 目视验证手段，避免盲目重构引入回归，建议作为下一迭代） |
| P2-9 | 死代码 / 保存反馈 / host_platform 缓存 | ✅ |
| P2-10 | CONTRIBUTING + CHANGELOG + issue 模板 | ✅；**i18n 评估：⏭ 暂缓**——目标用户为中文离线交付场景，当前无英文需求信号，待有国际化需求时再抽 gettext 串表（避免 YAGNI） |

---

## 五、剩余风险与建议

1. **GUI 目视冒烟已通过**（2026-08-17，`flet run -w` + 无头浏览器逐帧核验）：
   - ✅ 全量 UI 渲染正常：侧边栏（镜像输入框、9 个架构胶囊且 amd64 选中态高亮、导出设置卡片、开始执行按钮）、Tab、空状态，无白屏/重叠/错位；
   - ✅ **status_banner 状态横幅卡片正确显示**（接入布局的变更经目视确认，「准备就绪/等待任务开始」+进度条）；
   - ✅ **SnackBar 修复端到端生效**：空输入点击「开始执行」弹出红色提示条「请先输入至少一个镜像名称」；
   - ✅ **关于对话框版本单一来源生效**：弹出并显示「版本: v1.2.0」。
   - 未执行项：主题切换/架构对照表弹窗目视（对应逻辑均有单测覆盖，风险低）。
2. **`_resolve_docker_path` 真实文件系统分支**未覆盖（66-77%，路径依赖本机环境），属可接受残留。
3. **多架构同镜像 + cleanup=True** 时逐平台重复拉取（rmi 后无本地缓存复用），效率可再优化（digest 暂存或 containerd store），已在报告 4.2 节说明，非缺陷。
4. **远端 CI 已验证全绿**（2026-08-17，commit `a2233d2`）：11 个 job 全部成功——
   Lint (ruff)、Type check (mypy)、Test 矩阵 3 OS（ubuntu/windows/macos）× Python 3.10/3.11/3.12
   （各含 `--cov-fail-under=80` 覆盖率门禁）。首次运行发现的 Windows 测试可移植性问题
   （硬编码 `/tmp` 与路径分隔符断言、PTY 专属用例未跳过）已修复，均为测试问题而非生产代码缺陷。

---

*本文件由整改流程生成；每个 ✅ 项均有对应测试或 grep 证据，可复查。*
