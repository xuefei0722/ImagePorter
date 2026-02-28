# ImagePorter 原生应用构建指南

借助于 Flet 的强大特性，你可以将 `ImagePorter` Python 脚本打包为你操作系统所属的原生应用（例如 macOS 的 `.app` 文件）。以下是以 macOS 为例的详细构建步骤。

## 🛠 一、 构建前置准备

在开始打包之前，请确保你的系统满足以下条件：

1. **操作系统**：`flet build macos` 命令仅能在 macOS 机器上运行。
2. **Xcode**：你需要安装 Xcode（建议版本 15 或更高）。可从 Mac App Store 免费下载。
   - *重要提示：安装后请务必打开运行一次，以接受许可协议并自动初始化命令行工具。*
3. **CocoaPods**：版本需 1.16 或更高（用于编译依赖的插件）。
   ```bash
   brew install cocoapods 
   # 或 
   sudo gem install cocoapods
   ```
4. **Flutter SDK**：Flet 底层依赖 Flutter 进行打包。如果你之前没有安装过 Flutter，`flet build` 命令在第一次运行时会自动为你下载和配置。
5. **Apple Silicon 补充（M1/M2/M3等）**：如果你使用的是 Apple 芯片的 Mac，极大概率需要预先安装 Rosetta 2 翻译层：
   ```bash
   softwareupdate --install-rosetta
   ```

## � 二、 开发环境与依赖配置（推荐 venv）

Flet 在构建原生 `.app` 时，会将当前 Python 环境中所有的依赖打包。**如果环境臃肿，会导致构建出来的包体肥大。**
强烈推荐使用原生 `venv` 作为隔离环境，绝不要使用 Conda 此类包含复杂底层库的系统：

1. **创建并激活极简的虚拟环境**：
   打开终端，在项目根目录下运行以下命令（不用担心提交，`.venv` 已被 `.gitignore` 保护）：
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **安装核心依赖**：
   在环境激活状态下执行：
   ```bash
   pip install -r requirements.txt
   ```

## �🚀 三、 执行打包命令

我们在仓库中已经为你准备好了符合规范的目录结构（包含 `main.py`、`requirements.txt` 和 `assets/icon.png`）。

1. 打开终端（Terminal），将工作目录切换到项目根目录，**并确保上方你创建的 `.venv` 处于激活状态 (终端前缀显示为 `(.venv)`)**。
   ```bash
   cd /path/to/ImagePorter
   ```

2. 运行 Flet 打包命令，并指定打包参数（如下指令会自动把图标注入）：
   ```bash
   flet build macos --icon assets/icon.png
   ```

> **注意：** 初次运行此命令可能会耗费 5~15 分钟不等。因为 Flet 会在后台下载对应的 Flutter 环境并进行漫长的首次构建。后续构建速度会大幅提升。

## 📦 三、 获取应用程序

编译指令成功结束后，你可以在项目目录下看到自动生成了一个 `build/` 文件夹。

最终生成的独立的 macOS 应用程序包将会保存在这里：
```
build/macos/ImagePorter.app
```
*(包名默认与项目目录名或我们在 Flet 参数中配置的名称一致)*

你可以直接将这个 `.app` 文件拖放进入你的“应用程序 (Applications)” 文件夹中，双击即可像普通 Mac 软件一样直接运行！
