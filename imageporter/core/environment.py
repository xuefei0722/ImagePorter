"""系统与 Docker 环境信息：供侧边栏状态卡片与 --check-env 自检使用。"""

from __future__ import annotations

import platform as _platform
from dataclasses import dataclass

from imageporter.core.docker import DockerEnvStatus, probe_docker_environment

# platform.system() 原始值 → 展示名
_OS_DISPLAY = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}

_DOCKER_DESKTOP_URL = "https://www.docker.com/products/docker-desktop/"


@dataclass(frozen=True)
class SystemInfo:
    """宿主操作系统摘要。"""

    os_name: str
    os_release: str
    machine: str

    @property
    def display(self) -> str:
        """卡片展示用的一行摘要，如 'macOS 25.5.0 · arm64'。"""
        return f"{self.os_name} {self.os_release} · {self.machine}"


def get_system_info() -> SystemInfo:
    """采集当前系统信息（纯本地，无 IO）。"""
    raw = _platform.system()
    return SystemInfo(
        os_name=_OS_DISPLAY.get(raw, raw or "未知系统"),
        os_release=_platform.release() or "-",
        machine=_platform.machine() or "-",
    )


def format_environment_report(system: SystemInfo, docker: DockerEnvStatus) -> str:
    """生成人类可读的环境自检报告（--check-env 输出）。"""
    lines = [
        "ImagePorter 环境自检",
        f"  系统      : {system.display}",
        f"  Python    : {_platform.python_version()}",
    ]
    if not docker.installed:
        lines += [
            "  Docker    : ✗ 未安装",
            "",
            f"提示: 请先安装 Docker Desktop ({_DOCKER_DESKTOP_URL})",
        ]
    elif not docker.running:
        lines += [
            f"  Docker CLI: {docker.cli_version or '未知'}",
            "  守护进程  : ✗ 未运行",
            "",
            "提示: 请启动 Docker Desktop 后重新执行本检查。",
        ]
    else:
        lines += [
            f"  Docker CLI: {docker.cli_version or '未知'}",
            f"  守护进程  : ✓ 运行中（服务端 {docker.server_version}）",
            f"  主机平台  : {docker.host_platform}",
        ]
    return "\n".join(lines)


def run_environment_check() -> None:
    """执行环境自检并打印报告（--check-env 入口）。"""
    print(format_environment_report(get_system_info(), probe_docker_environment()))
