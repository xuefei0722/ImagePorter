# 鲸舟 (ImagePorter)

[![CI](https://github.com/xuefei0722/ImagePorter/actions/workflows/ci.yml/badge.svg)](https://github.com/xuefei0722/ImagePorter/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Flet](https://img.shields.io/badge/flet-0.81.0-green.svg)

> **ImagePorter (鲸舟)** 是一款基于 [Flet](https://flet.dev/) 构建的 Docker 镜像拉取与导出可视化工具。专为具有内网断网环境、需要频繁向离线环境传输 Docker 镜像的开发者设计。

## 🌟 核心特性

- **可视化多架构支持**：支持同时勾选并导出 `amd64`、`arm64/v8`、`arm/v7` 等 Docker Hub 常见架构标识。
- **并发任务引擎**：内置并发机制，支持同时 `pull` 和 `save` 多个镜像，显著提升离线打包效率。
- **可中止任务执行**：运行中可一键中止，界面状态与后台 Docker 子进程保持一致，不会“界面中止但后台继续”。
- **实时日志与进度条**：使用 PTY 伪终端技术，完美捕获并展示 Docker 命令的层级（Layer）下载进度。
- **主题切换与记忆**：支持亮色/暗色主题切换，并在重启后保留上次主题选择。
- **跨平台桌面体验**：借助 Flet 与 Flutter 的力量，体验极其流畅的桌面端原生 UI 交互。

## 🚀 快速开始

### 前置依赖

运行本项目需要您的机器上已安装：
- **Python** $\ge$ 3.10
- **Docker** 环境 (请确保 Docker 进程正在运行且当前用户有权限执行命令)

### 本地直接运行

1. 克隆本仓库到本地：
```bash
git clone https://github.com/xuefei0722/ImagePorter.git
cd ImagePorter
```

2. 安装与配置 Python 虚拟环境（推荐使用原生 `venv`，避免全局环境污染和后期打包臃肿）：
```bash
python3 -m venv .venv
source .venv/bin/activate

# 仅运行应用
pip install -r requirements.txt

# 开发（含测试 / lint / 类型检查工具链）
pip install -e ".[dev]"
```

3. 启动应用：
```bash
flet run main.py
```

4. 运行测试与质量检查（无需本机 Docker，测试全部为 mock 交互）：
```bash
python -m pytest tests/ -v --cov=imageporter --cov-fail-under=80
ruff check .
mypy
```

## 📦 构建为原生应用 (macOS / Windows / Linux)

如果你希望将 ImagePorter 编译为无需安装 Python 和依赖的独立桌面应用（如 `.app`、`.exe`），请参阅我们详细的构建指南：

👉 [**原生应用构建指南 (Build Guide)**](./docs/BUILD_GUIDE.md)

## 🤝 贡献指南

我们非常欢迎以 Issue 或 Pull Request 的形式提交你的建议与代码改进。在提交 PR 之前，请确保您的代码风格符合标准的 Python 规范。

## 📌 说明

- `requirements.txt` 仅包含 Python 运行时依赖（当前固定为 `flet==0.81.0`）；依赖的单一来源为 `pyproject.toml`，两者保持同步。
- Docker 依赖的是本机 Docker CLI，而不是 Python `docker` SDK 包；启动任务前会自动探测 Docker 守护进程是否在运行。
- **环境感知**：侧边栏底部「环境状态」卡片实时展示系统版本/架构与 Docker 安装、运行状态、服务端版本和主机平台（🟢 运行中 / 🔴 未运行 / ⚪ 未安装），支持手动刷新；应用启动与每次任务结束后会自动探测。
- **环境自检**：`python main.py --check-env` 输出系统/Docker 环境报告，用于安装排障。
- 层级（Layer）下载进度条基于 Unix PTY 伪终端捕获；Windows 下自动降级为逐行日志展示。

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。详细内容请参阅 LICENSE 文件。
