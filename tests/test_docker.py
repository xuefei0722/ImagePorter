"""Tests for imageporter.core.docker — pure / mockable functions only.

NOTE: These tests mock Docker interactions; no real Docker daemon required.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch

# We must be able to import the module even without Docker installed.
# The module does conditional `import pty` which is fine.
from imageporter.core.docker import (
    _ANSI_RE,
    _HAS_PTY,
    _build_exec_env,
    _env_cache,
    _normalize_cmd,
    _run_docker_interactive,
    build_tar_path,
    check_docker_available,
    choose_platforms,
    get_host_platform,
    get_image_platforms,
    run_cmd,
)


class TestAnsiRegex(unittest.TestCase):
    def test_strip_color(self):
        self.assertEqual(_ANSI_RE.sub("", "\x1b[32mHello\x1b[0m"), "Hello")

    def test_strip_bold_color(self):
        self.assertEqual(_ANSI_RE.sub("", "\x1b[1;31mError\x1b[0m"), "Error")

    def test_no_ansi_unchanged(self):
        self.assertEqual(_ANSI_RE.sub("", "No ANSI here"), "No ANSI here")

    def test_strip_osc_title(self):
        self.assertEqual(_ANSI_RE.sub("", "\x1b]0;title\x07real text"), "real text")

    def test_strip_cursor_show(self):
        self.assertEqual(_ANSI_RE.sub("", "\x1b[?25hDone"), "Done")


class TestBuildExecEnv(unittest.TestCase):
    def test_docker_cli_hints_disabled(self):
        env = _build_exec_env()
        self.assertEqual(env["DOCKER_CLI_HINTS"], "false")

    def test_path_present(self):
        env = _build_exec_env()
        self.assertIn("PATH", env)


class TestNormalizeCmd(unittest.TestCase):
    def test_non_docker_unchanged(self):
        self.assertEqual(_normalize_cmd(["ls", "-la"]), ["ls", "-la"])

    def test_empty_cmd(self):
        self.assertEqual(_normalize_cmd([]), [])


class TestBuildTarPath(unittest.TestCase):
    """路径断言使用 os.path.join 以兼容 Windows 分隔符。"""

    def test_simple(self):
        path = build_tar_path("nginx:latest", "linux/amd64", "/tmp/out")
        self.assertEqual(path, os.path.join("/tmp/out", "nginx_latest_linux_amd64.tar"))

    def test_no_tag(self):
        path = build_tar_path("nginx", "linux/arm64", "/tmp/out")
        self.assertEqual(path, os.path.join("/tmp/out", "nginx_latest_linux_arm64.tar"))

    def test_registry_prefix(self):
        path = build_tar_path("ghcr.io/owner/app:v1", "linux/amd64", "/output")
        self.assertEqual(path, os.path.join("/output", "ghcr.io_owner_app_v1_linux_amd64.tar"))

    def test_ends_with_tar(self):
        path = build_tar_path("redis:7", "linux/amd64", "/home/user/exports")
        self.assertTrue(path.startswith(os.path.join("/home/user/exports", "")))
        self.assertTrue(path.endswith(".tar"))


class TestCheckDockerAvailable(unittest.TestCase):
    def setUp(self):
        _env_cache["docker_ok"] = None
        _env_cache["docker_msg"] = ""
        _env_cache["docker_path"] = None
        _env_cache["host_platform"] = None

    def tearDown(self):
        _env_cache["docker_ok"] = None
        _env_cache["docker_msg"] = ""
        _env_cache["docker_path"] = None
        _env_cache["host_platform"] = None

    def test_cached_positive_skips_probe(self):
        _env_cache["docker_ok"] = True
        with patch("imageporter.core.docker.run_cmd") as mock_run:
            ok, msg = check_docker_available()
            self.assertTrue(ok)
            self.assertEqual(msg, "")
            mock_run.assert_not_called()

    @patch("imageporter.core.docker._resolve_docker_path", return_value=None)
    def test_not_found(self, _):
        ok, msg = check_docker_available()
        self.assertFalse(ok)
        self.assertIn("未找到", msg)

    @patch("imageporter.core.docker.run_cmd", return_value=(True, "27.0.0"))
    @patch("imageporter.core.docker._resolve_docker_path", return_value="/usr/bin/docker")
    def test_found_with_daemon_running(self, _, __):
        ok, msg = check_docker_available()
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    @patch("imageporter.core.docker.run_cmd", return_value=(False, ""))
    @patch("imageporter.core.docker._resolve_docker_path", return_value="/usr/bin/docker")
    def test_daemon_not_running(self, _, __):
        """H-2：二进制存在但守护进程未运行时应明确报错。"""
        ok, msg = check_docker_available()
        self.assertFalse(ok)
        self.assertIn("守护进程未运行", msg)

    @patch("imageporter.core.docker.run_cmd", return_value=(False, ""))
    @patch("imageporter.core.docker._resolve_docker_path", return_value="/usr/bin/docker")
    def test_failure_not_cached_self_heals(self, _, mock_run):
        """H-2：失败不缓存，用户启动 Docker 后无需重启应用。"""
        self.assertFalse(check_docker_available()[0])
        self.assertFalse(check_docker_available()[0])
        self.assertEqual(mock_run.call_count, 2)
        mock_run.return_value = (True, "27.0.0")
        self.assertTrue(check_docker_available()[0])


class TestGetHostPlatform(unittest.TestCase):
    def setUp(self):
        _env_cache["host_platform"] = None

    def tearDown(self):
        _env_cache["host_platform"] = None

    @patch("imageporter.core.docker.run_cmd", return_value=(False, ""))
    def test_failure_returns_default_without_caching(self, mock_run):
        """M-5：探测失败返回默认值但不缓存，下次自动重试。"""
        self.assertEqual(get_host_platform(), "linux/amd64")
        self.assertEqual(get_host_platform(), "linux/amd64")
        self.assertEqual(mock_run.call_count, 2)

    @patch("imageporter.core.docker.run_cmd", return_value=(True, "linux/arm64\n"))
    def test_success_cached(self, mock_run):
        self.assertEqual(get_host_platform(), "linux/arm64")
        self.assertEqual(get_host_platform(), "linux/arm64")
        self.assertEqual(mock_run.call_count, 1)


class TestRunCmd(unittest.TestCase):
    @patch("imageporter.core.docker.subprocess.run")
    @patch("imageporter.core.docker._normalize_cmd", side_effect=lambda c: c)
    def test_success(self, _, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        ok, out = run_cmd(["echo", "hi"])
        self.assertTrue(ok)
        self.assertIn("OK", out)

    @patch("imageporter.core.docker.subprocess.run")
    @patch("imageporter.core.docker._normalize_cmd", side_effect=lambda c: c)
    def test_failure(self, _, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
        ok, out = run_cmd(["bad", "cmd"])
        self.assertFalse(ok)
        self.assertIn("error msg", out)

    @patch("imageporter.core.docker.subprocess.run", side_effect=OSError("not found"))
    @patch("imageporter.core.docker._normalize_cmd", side_effect=lambda c: c)
    def test_exception(self, _, __):
        ok, out = run_cmd(["missing"])
        self.assertFalse(ok)
        self.assertIn("not found", out)


class TestGetImagePlatforms(unittest.TestCase):
    @patch("imageporter.core.docker.run_cmd")
    def test_success(self, mock_run):
        manifest = {
            "manifests": [
                {"platform": {"os": "linux", "architecture": "amd64"}},
                {"platform": {"os": "linux", "architecture": "arm64"}},
            ]
        }
        mock_run.return_value = (True, json.dumps(manifest))
        platforms, err = get_image_platforms("nginx")
        self.assertIn("linux/amd64", platforms)
        self.assertIn("linux/arm64", platforms)
        self.assertEqual(err, "")

    @patch("imageporter.core.docker.run_cmd")
    def test_not_available(self, mock_run):
        mock_run.return_value = (False, "no manifest")
        platforms, err = get_image_platforms("private/image")
        self.assertEqual(platforms, [])
        self.assertIn("不可用", err)

    @patch("imageporter.core.docker.run_cmd")
    def test_invalid_json(self, mock_run):
        mock_run.return_value = (True, "not json{{{")
        platforms, err = get_image_platforms("nginx")
        self.assertEqual(platforms, [])
        self.assertIn("失败", err)

    @patch("imageporter.core.docker.run_cmd")
    def test_unknown_attestation_platforms_filtered(self, mock_run):
        """M-6：attestation 产物（unknown/unknown）不应计入可用架构。"""
        manifest = {
            "manifests": [
                {"platform": {"os": "linux", "architecture": "amd64"}},
                {"platform": {"os": "unknown", "architecture": "unknown"}},
                {"platform": {"architecture": "amd64"}},  # 缺 os 字段
            ]
        }
        mock_run.return_value = (True, json.dumps(manifest))
        platforms, err = get_image_platforms("nginx")
        self.assertEqual(platforms, ["linux/amd64"])
        self.assertEqual(err, "")


class TestChoosePlatforms(unittest.TestCase):
    @patch("imageporter.core.docker.get_image_platforms")
    def test_no_selection_picks_common(self, mock_gip):
        mock_gip.return_value = (["linux/386", "linux/amd64", "linux/arm64", "linux/s390x"], "")
        result, _ = choose_platforms("nginx", [], "linux/amd64")
        self.assertIn("linux/amd64", result)
        self.assertIn("linux/arm64", result)
        self.assertNotIn("linux/386", result)

    @patch("imageporter.core.docker.get_image_platforms")
    def test_no_selection_no_avail_uses_host(self, mock_gip):
        mock_gip.return_value = ([], "")
        result, _ = choose_platforms("nginx", [], "linux/riscv64")
        self.assertEqual(result, ["linux/riscv64"])

    @patch("imageporter.core.docker.get_image_platforms")
    def test_selected_intersects_available(self, mock_gip):
        mock_gip.return_value = (["linux/amd64", "linux/arm64"], "")
        result, _ = choose_platforms("nginx", ["linux/amd64", "linux/s390x"], "linux/amd64")
        self.assertEqual(result, ["linux/amd64"])

    @patch("imageporter.core.docker.get_image_platforms")
    def test_no_overlap_returns_selected(self, mock_gip):
        mock_gip.return_value = (["linux/amd64"], "")
        result, _ = choose_platforms("nginx", ["linux/s390x"], "linux/amd64")
        self.assertEqual(result, ["linux/s390x"])


class TestRunDockerInteractive(unittest.TestCase):
    """跨平台运行器（Unix PTY / Windows PIPE 降级）的真实子进程测试。"""

    def test_completes_and_captures_output(self):
        cmd = [sys.executable, "-c", "print('hello-line')"]
        ok, out = _run_docker_interactive(cmd)
        self.assertTrue(ok)
        self.assertIn("hello-line", out)

    def test_nonzero_exit_reports_failure(self):
        cmd = [sys.executable, "-c", "import sys; sys.exit(3)"]
        ok, out = _run_docker_interactive(cmd)
        self.assertFalse(ok)

    def test_stop_event_terminates_long_process(self):
        cmd = [sys.executable, "-c", "import time; time.sleep(30)"]
        stop = threading.Event()
        stop.set()
        ok, out = _run_docker_interactive(cmd, stop_event=stop)
        self.assertFalse(ok)
        self.assertIn("[中止]", out)

    def test_line_callback_receives_output(self):
        cmd = [sys.executable, "-c", "print('cb-line')"]
        lines: list[str] = []
        ok, _ = _run_docker_interactive(cmd, line_cb=lines.append)
        self.assertTrue(ok)
        self.assertIn("cb-line", lines)

    @unittest.skipIf(not _HAS_PTY, "行内 \\r 进度覆写是 PTY 专属行为（Windows 走 PIPE 降级）")
    def test_carriage_return_progress_keeps_last_segment(self):
        """PTY 行内 \\r 进度覆写应保留最后一段非空内容（CRLF 丢行修复的回归防护）。"""
        cmd = [sys.executable, "-c", "print('45%\\r78%')"]
        ok, out = _run_docker_interactive(cmd)
        self.assertTrue(ok)
        self.assertIn("78%", out)
        self.assertNotIn("45%", out)


class TestRunPipeDocker(unittest.TestCase):
    """Windows 降级路径（PIPE）同样在 Unix 下可执行，直接验证其行为。"""

    def test_completes_and_captures_output(self):
        from imageporter.core.docker import _run_pipe_docker
        ok, out = _run_pipe_docker([sys.executable, "-c", "print('pipe-line')"])
        self.assertTrue(ok)
        self.assertIn("pipe-line", out)

    def test_stop_event_terminates(self):
        """PIPE 路径：静默进程也必须能被及时中止（读线程轮询修复的回归防护）。"""
        from imageporter.core.docker import _run_pipe_docker
        stop = threading.Event()
        stop.set()
        ok, out = _run_pipe_docker([sys.executable, "-c", "import time; time.sleep(30)"], stop_event=stop)
        self.assertFalse(ok)
        self.assertIn("[中止]", out)

    def test_popen_failure_returns_error(self):
        from imageporter.core.docker import _run_pipe_docker
        ok, out = _run_pipe_docker(["/nonexistent/binary/xyz"])
        self.assertFalse(ok)


class TestDockerWrappers(unittest.TestCase):
    """docker_pull / docker_save / docker_remove 的命令构造正确性。"""

    @patch("imageporter.core.docker._run_docker_interactive", return_value=(True, "ok"))
    def test_docker_pull_command(self, mock_run):
        from imageporter.core.docker import docker_pull
        ok, _ = docker_pull("nginx", "linux/arm64")
        self.assertTrue(ok)
        mock_run.assert_called_once_with(
            ["docker", "pull", "--platform", "linux/arm64", "nginx"],
            None,
            stop_event=None,
        )

    @patch("imageporter.core.docker._run_docker_interactive", return_value=(True, "ok"))
    def test_docker_save_command(self, mock_run):
        from imageporter.core.docker import docker_save
        ok, path, _ = docker_save("nginx", "linux/amd64", "/tmp/out")
        self.assertTrue(ok)
        expected = os.path.join("/tmp/out", "nginx_latest_linux_amd64.tar")
        self.assertEqual(path, expected)
        mock_run.assert_called_once_with(
            ["docker", "save", "-o", expected, "nginx"],
            None,
            stop_event=None,
        )

    @patch("imageporter.core.docker.run_cmd", return_value=(True, "ok"))
    def test_docker_remove_command(self, mock_run):
        from imageporter.core.docker import docker_remove
        docker_remove("nginx")
        mock_run.assert_called_once_with(["docker", "rmi", "nginx"])


if __name__ == "__main__":
    unittest.main()
