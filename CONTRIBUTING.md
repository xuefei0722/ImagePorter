# 贡献指南

感谢你愿意为 ImagePorter（鲸舟）贡献代码！请花几分钟了解以下约定。

## 环境准备

```bash
git clone https://github.com/xuefei0722/ImagePorter.git
cd ImagePorter
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

> 测试全程 mock Docker 交互，本机无需安装 Docker 或运行守护进程。

## 开发工作流

1. 从 `main` 切出特性分支：`git checkout -b feat/your-feature`。
2. 修改代码。约定：
   - `imageporter/core/` 不得依赖 flet；新增业务逻辑优先落在 `core/` 并配套测试；
   - 所有 subprocess 使用列表参数，镜像名一律先经 `parser` 校验；
   - UI 刷新只发生在 `main.py` 的 `ui_pump` 单写者循环，工作线程只 `emit()`。
3. 本地跑通三大门禁（与 CI 完全一致）：
   ```bash
   python -m pytest tests/ -v --cov=imageporter --cov-fail-under=80
   ruff check .
   mypy
   ```
4. 提交信息遵循约定式提交（Conventional Commits）：`feat: ...`、`fix: ...`、
   `docs: ...`、`test: ...`、`refactor: ...`、`chore: ...`。
5. 发起 Pull Request，描述变更动机与测试证据；新功能请附测试。

## 提交前检查清单

- [ ] 新增/变更的行为有对应测试
- [ ] 三大门禁本地全部通过（pytest+coverage / ruff / mypy）
- [ ] 无硬编码密钥、无 `shell=True`、无静默吞错（必要的兜底 except 请注释原因）
- [ ] 涉及 UI 文案变更时同时更新 README（如行为描述受影响）

## 报告问题

请使用 GitHub Issues 的 bug / feature 模板，并附上：

- 操作系统与 Python、Docker 版本
- 复现步骤与期望/实际行为
- 如有报错，附「运行日志」页的输出

## 许可

提交即表示你同意以 [MIT License](LICENSE) 发布你的贡献。
