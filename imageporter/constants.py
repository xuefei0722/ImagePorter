"""全局常量与设计令牌。"""

from __future__ import annotations

import os
import sys

# --- 窗口与布局 ---
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
SIDEBAR_WIDTH = 320

# --- 性能调优 ---
MAX_LOG_LINES = 2000
SELECT_TIMEOUT = 0.2
READ_BUFFER_SIZE = 4096
EVENT_BATCH_LIMIT = 500
UI_PUMP_INTERVAL = 0.05
MAX_CONCURRENCY = 8
MIN_CONCURRENCY = 1

# --- Docker 探测 ---
DAEMON_PROBE_TIMEOUT = 8.0
ENV_RETRY_INTERVAL = 10.0

# --- 文件与缓存路径 ---
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".imageporter")
PREFS_FILE = os.path.join(CACHE_DIR, "prefs.json")

# --- Docker CLI 路径提示 ---
DOCKER_PATH_HINTS_UNIX = [
    "/usr/local/bin/docker",
    "/opt/homebrew/bin/docker",
    "/Applications/Docker.app/Contents/Resources/bin/docker",
]
DOCKER_PATH_HINTS_WIN = [
    r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
    r"C:\ProgramData\DockerDesktop\version-bin\docker.exe",
]
DOCKER_PATH_HINTS = DOCKER_PATH_HINTS_WIN if sys.platform == "win32" else DOCKER_PATH_HINTS_UNIX

# --- 平台架构列表 ---
PLATFORM_OPTIONS = [
    "linux/amd64", "linux/arm64", "linux/arm/v7", "linux/arm/v6", "linux/arm/v5",
    "linux/386", "linux/ppc64le", "linux/s390x", "linux/riscv64",
]

PLATFORM_LABELS: dict[str, tuple[str, str]] = {
    "linux/amd64": ("amd64", "Docker Hub: linux/amd64 | x86-64 (AMD64) 64 位 Intel/AMD 架构"),
    "linux/arm64": ("arm64/v8", "Docker Hub 常见写法: linux/arm64/v8 | AArch64 64 位 ARM 架构"),
    "linux/arm/v7": ("arm/v7", "Docker Hub: linux/arm/v7 | 32 位 ARMv7 架构"),
    "linux/arm/v6": ("arm/v6", "Docker Hub: linux/arm/v6 | 32 位 ARMv6 旧架构"),
    "linux/arm/v5": ("arm/v5", "Docker Hub: linux/arm/v5 | 32 位 ARMv5 旧架构（更老设备）"),
    "linux/386": ("386", "Docker Hub: linux/386 | x86 (IA-32) 32 位架构"),
    "linux/ppc64le": ("ppc64le", "Docker Hub: linux/ppc64le | PowerPC 64 LE（小端）"),
    "linux/s390x": ("s390x", "Docker Hub: linux/s390x | IBM Z 64 位架构"),
    "linux/riscv64": ("riscv64", "Docker Hub: linux/riscv64 | RISC-V 64 位架构"),
}

ARCH_REFERENCE_ROWS = [
    ("linux/amd64", "amd64", "x86-64 (Intel/AMD 64 位)"),
    ("linux/arm64", "arm64/v8", "AArch64 (ARM 64 位)"),
    ("linux/arm/v7", "arm/v7", "ARMv7 (32 位)"),
    ("linux/arm/v6", "arm/v6", "ARMv6 (32 位旧架构)"),
    ("linux/arm/v5", "arm/v5", "ARMv5 (32 位更老架构)"),
    ("linux/386", "386", "x86 (IA-32, 32 位)"),
    ("linux/ppc64le", "ppc64le", "PowerPC 64 LE"),
    ("linux/s390x", "s390x", "IBM Z 大型机 64 位"),
    ("linux/riscv64", "riscv64", "RISC-V 64 位"),
]
