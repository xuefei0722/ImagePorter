# 鲸舟 (ImagePorter)

![License](https://img.shields.io/github/license/xuefei/ImagePorter)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Flet](https://img.shields.io/badge/flet-latest-green.svg)

> **ImagePorter (鲸舟)** 是一款基于 [Flet](https://flet.dev/) 构建的 Docker 镜像拉取与导出可视化工具。专为具有内网断网环境、需要频繁向离线环境传输 Docker 镜像的开发者设计。

## 🌟 核心特性

- **可视化多架构支持**：支持同时勾选并导出 `linux/amd64`、`linux/arm64` 等多种架构的镜像。
- **并发任务引擎**：内置并发机制，支持同时 `pull` 和 `save` 多个镜像，显著提升离线打包效率。
- **智能镜像校验**：自动校验输入镜像的合法性，剔除格式错误的条目；支持智能检测远端镜像可用的架构。
- **实时日志与进度条**：使用 PTY 伪终端技术，完美捕获并展示 Docker 命令的层级（Layer）下载进度。
- **跨平台桌面体验**：借助 Flet 与 Flutter 的力量，体验极其流畅的桌面端原生 UI 交互。

## 🚀 快速开始

### 前置依赖

运行本项目需要您的机器上已安装：
- **Python** $\ge$ 3.10
- **Docker** 环境 (请确保 Docker 进程正在运行且当前用户有权限执行命令)

### 本地直接运行

1. 克隆本仓库到本地：
```bash
git clone https://github.com/USER/ImagePorter.git
cd ImagePorter
```

2. 安装所需 Python 依赖：
```bash
pip install -r requirements.txt
```

3. 启动应用：
```bash
flet run main.py
```

## 📦 构建为原生应用 (macOS / Windows / Linux)

如果你希望将 ImagePorter 编译为无需安装 Python 和依赖的独立桌面应用（如 `.app`、`.exe`），请参阅我们详细的构建指南：

👉 [**原生应用构建指南 (Build Guide)**](./docs/BUILD_GUIDE.md)

## �� 贡献指南

我们非常欢迎以 Issue 或 Pull Request 的形式提交你的建议与代码改进。在提交 PR 之前，请确保您的代码风格符合标准的 Python 规范。

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。详细内容请参阅 LICENSE 文件。
