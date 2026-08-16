"""Docker 相关的核心逻辑：路径解析、命令执行、镜像操作。"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from queue import Empty, Queue
from typing import Any

# --- 跨平台兼容：PTY 仅在 Unix 系统可用 ---
if sys.platform != "win32":
    import pty
    import select
    _HAS_PTY = True
else:
    _HAS_PTY = False

from imageporter.constants import (
    DAEMON_PROBE_TIMEOUT,
    DOCKER_PATH_HINTS,
    READ_BUFFER_SIZE,
    SELECT_TIMEOUT,
)

# --- ANSI 转义码清理正则 ---
_ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07')

# --- 环境缓存（键类型异构：docker_ok 为 bool、其余为 str/None） ---
_env_cache: dict[str, Any] = {
    "docker_ok": None,
    "docker_msg": "",
    "host_platform": None,
    "docker_path": None,
}


def _build_exec_env() -> dict[str, str]:
    """构建执行环境变量，添加 Docker 路径提示到 PATH。"""
    env = dict(os.environ)
    path_sep = ";" if sys.platform == "win32" else ":"
    current_path = env.get("PATH", "")
    path_items = current_path.split(path_sep) if current_path else []
    extras = [os.path.dirname(p) for p in DOCKER_PATH_HINTS]
    missing = [p for p in extras if p not in path_items]
    if missing:
        env["PATH"] = (
            f"{current_path}{path_sep}{path_sep.join(missing)}"
            if current_path
            else path_sep.join(missing)
        )
    env["DOCKER_CLI_HINTS"] = "false"
    return env


def _resolve_docker_path() -> str | None:
    """解析 Docker 可执行文件的完整路径（支持缓存）。"""
    cached = _env_cache.get("docker_path")
    if isinstance(cached, str) and cached:
        return cached
    which_path = shutil.which("docker", path=_build_exec_env().get("PATH"))
    candidates = [which_path, *DOCKER_PATH_HINTS]
    for candidate in candidates:
        if not candidate:
            continue
        real = os.path.expanduser(candidate)
        if os.path.isfile(real) and os.access(real, os.X_OK):
            _env_cache["docker_path"] = real
            return real
    return None


def _normalize_cmd(cmd: list[str]) -> list[str]:
    """将命令中的 'docker' 替换为完整路径。"""
    if cmd and cmd[0] == "docker":
        docker_path = _resolve_docker_path()
        if docker_path:
            return [docker_path, *cmd[1:]]
    return cmd


def check_docker_available() -> tuple[bool, str]:
    """检查 Docker CLI 与守护进程是否可用。

    正向结果缓存以避免重复探测；失败不缓存，便于用户启动 Docker 后自愈。
    """
    if _env_cache["docker_ok"] is True:
        return True, ""
    docker_path = _resolve_docker_path()
    if not docker_path:
        msg = "未找到 docker 命令（请确认 Docker Desktop 已安装）"
        _env_cache["docker_ok"] = False
        _env_cache["docker_msg"] = msg
        return False, msg
    # 二进制存在 ≠ 守护进程在运行：用 docker info 做真实健康检查
    ok, _ = run_cmd(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        timeout=DAEMON_PROBE_TIMEOUT,
    )
    if not ok:
        msg = "Docker 守护进程未运行（请启动 Docker Desktop 后重试）"
        _env_cache["docker_ok"] = False
        _env_cache["docker_msg"] = msg
        return False, msg
    _env_cache["docker_ok"] = True
    _env_cache["docker_msg"] = ""
    return True, ""


def run_cmd(cmd: list[str], timeout: float | None = None) -> tuple[bool, str]:
    """运行通用命令（无交互式输出）。"""
    normalized_cmd = _normalize_cmd(cmd)
    try:
        result = subprocess.run(
            normalized_cmd,
            capture_output=True,
            encoding="utf-8",
            timeout=timeout,
            env=_build_exec_env(),
        )
        return result.returncode == 0, (result.stdout or "") + (result.stderr or "")
    except Exception as e:
        return False, str(e)


def _run_pty_docker(
    cmd: list[str],
    line_cb=None,
    stop_event: threading.Event | None = None,
) -> tuple[bool, str]:
    """使用 PTY 伪终端运行 Docker 命令（Unix 专属），可捕获层级进度。"""
    normalized_cmd = _normalize_cmd(cmd)
    master_fd, slave_fd = pty.openpty()
    try:
        proc = subprocess.Popen(
            normalized_cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=subprocess.STDOUT,
            close_fds=True,
            env=_build_exec_env(),
        )
    except Exception as e:
        os.close(master_fd)
        os.close(slave_fd)
        return False, str(e)
    os.close(slave_fd)
    all_lines: list[str] = []
    buf = ""

    def _flush():
        nonlocal buf
        while "\n" in buf:
            raw, buf = buf.split("\n", 1)
            if "\r" in raw:
                # \r 分隔的是同一行内的进度覆写（如 45%\r67%\r78%），保留最后一段非空内容；
                # 直接取 split("\r")[-1] 会因行尾 CRLF 的空尾段丢掉整行
                parts = [p for p in raw.split("\r") if p]
                raw = parts[-1] if parts else ""
            clean = _ANSI_RE.sub("", raw).strip()
            if clean:
                all_lines.append(clean)
                if line_cb:
                    line_cb(clean)

    while True:
        if stop_event is not None and stop_event.is_set() and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            all_lines.append("[中止] 用户请求停止任务")
            break

        try:
            rlist, _, _ = select.select([master_fd], [], [], SELECT_TIMEOUT)
        except (OSError, ValueError):
            break
        if rlist:
            try:
                chunk = os.read(master_fd, READ_BUFFER_SIZE)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            _flush()
        elif proc.poll() is not None:
            break
    try:
        os.close(master_fd)
    except OSError:
        pass
    proc.wait()
    success = proc.returncode == 0
    if stop_event is not None and stop_event.is_set():
        success = False
    return success, "\n".join(all_lines)


def _run_pipe_docker(
    cmd: list[str],
    line_cb=None,
    stop_event: threading.Event | None = None,
) -> tuple[bool, str]:
    """使用 subprocess.PIPE 运行 Docker 命令（Windows 兼容降级方案）。

    读取放在独立线程、主循环轮询停止事件，确保静默进程（如长时间
    docker save 无输出）也能被及时中止，而不会被 readline 阻塞。
    """
    normalized_cmd = _normalize_cmd(cmd)
    try:
        proc = subprocess.Popen(
            normalized_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=_build_exec_env(),
        )
    except Exception as e:
        return False, str(e)
    all_lines: list[str] = []
    line_queue: Queue = Queue()

    def _reader() -> None:
        assert proc.stdout is not None  # stdout=PIPE 保证非空
        try:
            for raw_line in iter(proc.stdout.readline, b""):
                line_queue.put(raw_line)
        finally:
            line_queue.put(None)  # EOF 哨兵

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()

    stopped = False
    while True:
        if stop_event is not None and stop_event.is_set():
            stopped = True
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            all_lines.append("[中止] 用户请求停止任务")
            break
        try:
            raw_line = line_queue.get(timeout=SELECT_TIMEOUT)
        except Empty:
            # 暂无输出：若进程与读线程均已结束则收尾，否则继续轮询
            if proc.poll() is not None and not reader.is_alive():
                break
            continue
        if raw_line is None:
            break
        clean = _ANSI_RE.sub(
            "", raw_line.decode("utf-8", errors="replace")
        ).strip()
        if clean:
            all_lines.append(clean)
            if line_cb:
                line_cb(clean)

    try:
        if proc.stdout:
            proc.stdout.close()
    except Exception:
        pass
    proc.wait()
    success = proc.returncode == 0
    if stopped or (stop_event is not None and stop_event.is_set()):
        success = False
    return success, "\n".join(all_lines)


def _run_docker_interactive(
    cmd: list[str],
    line_cb=None,
    stop_event: threading.Event | None = None,
) -> tuple[bool, str]:
    """跨平台统一入口：Unix 使用 PTY，Windows 降级为 PIPE。"""
    if _HAS_PTY:
        return _run_pty_docker(cmd, line_cb, stop_event)
    return _run_pipe_docker(cmd, line_cb, stop_event)


def get_host_platform() -> str:
    """获取主机平台（OS/Architecture 格式）。

    探测失败时返回 amd64 默认值但不缓存，下次调用自动重试，
    避免 daemon 短暂无响应导致整会话平台判断错误。
    """
    cached = _env_cache.get("host_platform")
    if cached:
        return cached
    ok, out = run_cmd(
        ["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"]
    )
    if ok and out:
        platform = out.strip()
        _env_cache["host_platform"] = platform
        return platform
    return "linux/amd64"


def get_image_platforms(image: str) -> tuple[list[str], str]:
    """获取镜像支持的平台列表（来自 Docker Manifest）。"""
    ok, out = run_cmd(
        ["docker", "manifest", "inspect", image], timeout=8.0
    )
    if not ok:
        return [], "Manifest不可用"
    try:
        data = json.loads(out)
        platforms = set()
        for m in data.get("manifests", []):
            p = m.get("platform", {})
            os_name = p.get("os")
            arch = p.get("architecture")
            if not os_name or not arch:
                continue
            if os_name == "unknown" or arch == "unknown":
                # attestation/provenance 产物不是可拉取的目标架构
                continue
            platforms.add(f"{os_name}/{arch}")
        return sorted(platforms), ""
    except Exception:
        return [], "Manifest 解析失败"


def choose_platforms(
    image: str,
    selected: list[str],
    host: str,
) -> tuple[list[str], str]:
    """根据用户选择和镜像可用架构，返回最终的目标平台列表。"""
    avail, err = get_image_platforms(image)
    if not selected:
        if avail:
            return (
                [p for p in avail if "amd64" in p or "arm64" in p]
                or [avail[0]],
                "",
            )
        return [host], ""
    if not avail:
        return selected, ""
    matched = [p for p in avail if p in set(selected)]
    return matched if matched else selected, ""


def build_tar_path(image: str, platform: str, output_dir: str) -> str:
    """根据镜像名、平台和输出目录构建 .tar 文件路径。"""
    name = image.split(":")[0]
    tag = image.split(":")[1] if ":" in image else "latest"
    return os.path.join(
        output_dir,
        f"{name.replace('/', '_')}_{tag}_{platform.replace('/', '_')}.tar",
    )


def docker_pull(
    image: str,
    platform: str,
    line_cb=None,
    stop_event: threading.Event | None = None,
) -> tuple[bool, str]:
    """拉取指定平台的 Docker 镜像。"""
    return _run_docker_interactive(
        ["docker", "pull", "--platform", platform, image],
        line_cb,
        stop_event=stop_event,
    )


def docker_save(
    image: str,
    platform: str,
    output_dir: str,
    line_cb=None,
    stop_event: threading.Event | None = None,
) -> tuple[bool, str, str]:
    """将 Docker 镜像导出为 .tar 文件。"""
    path = build_tar_path(image, platform, output_dir)
    ok, out = _run_docker_interactive(
        ["docker", "save", "-o", path, image],
        line_cb,
        stop_event=stop_event,
    )
    return ok, path, out


def docker_remove(image: str) -> None:
    """删除本地 Docker 镜像。"""
    run_cmd(["docker", "rmi", image])
