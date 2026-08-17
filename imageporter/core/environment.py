"""系统与 Docker 环境信息：供侧边栏状态卡片与 --check-env 自检使用。"""

from __future__ import annotations

import os
import platform as _platform
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from imageporter.constants import ENV_RETRY_INTERVAL
from imageporter.core.docker import DockerEnvStatus, normalize_arch, probe_docker_environment

# platform.system() 原始值 → 展示名
_OS_DISPLAY = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}

DOCKER_DESKTOP_URL = "https://www.docker.com/products/docker-desktop/"
DOCKER_DOCS_URL = "https://docs.docker.com/get-started/get-docker/"

# Windows 下 Docker Desktop 可执行文件的常见安装位置
_WINDOWS_DESKTOP_EXE_HINTS = [
    r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
    r"C:\Program Files\Docker\Docker\frontend\Docker Desktop.exe",
]


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
    """采集当前系统信息（纯本地，无 IO）；架构名归一到 Docker Hub 词汇。"""
    raw = _platform.system()
    return SystemInfo(
        os_name=_OS_DISPLAY.get(raw, raw or "未知系统"),
        os_release=_platform.release() or "-",
        machine=normalize_arch(_platform.machine() or "-"),
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
            f"提示: 请先安装 Docker Desktop ({DOCKER_DESKTOP_URL})",
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


def can_launch_docker_desktop() -> bool:
    """当前平台是否支持自动启动 Docker Desktop（macOS/Windows）。"""
    return _platform.system() in ("Darwin", "Windows")


def launch_docker_desktop() -> bool:
    """尝试启动 Docker Desktop 应用（用户在状态卡片上显式点击触发）。"""
    system = _platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["open", "-a", "Docker"])
            return True
        if system == "Windows":
            for exe in _WINDOWS_DESKTOP_EXE_HINTS:
                if os.path.exists(exe):
                    startfile = getattr(os, "startfile", None)
                    if startfile is not None:
                        startfile(exe)  # noqa: S606 - 用户显式请求启动本机应用
                        return True
            return False
    except Exception:
        return False
    return False


class EnvRetryWatcher:
    """Docker 不可用时周期性重探，守护进程恢复运行后自动停止。

    通过 emit_status 回调输出最新探测结果（与手动刷新共用同一条
    ENV_STATUS 事件通道）；Event 防止多个 watcher 叠加。
    """

    def __init__(
        self,
        emit_status: Callable[[DockerEnvStatus], None],
        interval: float = ENV_RETRY_INTERVAL,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._emit_status = emit_status
        self._interval = interval
        self._sleep = sleeper
        self._active = threading.Event()

    @property
    def active(self) -> bool:
        return self._active.is_set()

    def maybe_start(self, status: DockerEnvStatus) -> None:
        """Docker 未运行时启动后台重试循环（已运行或循环已在跑则忽略）。"""
        if status.running or self._active.is_set():
            return
        self._active.set()
        threading.Thread(target=self._watch, daemon=True).start()

    def _watch(self) -> None:
        try:
            while True:
                self._sleep(self._interval)
                status = probe_docker_environment()
                self._emit_status(status)
                if status.running:
                    break
        finally:
            self._active.clear()
