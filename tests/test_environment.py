"""Tests for imageporter.core.environment — system info, check report & retry watcher."""

from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from imageporter.core.docker import DockerEnvStatus
from imageporter.core.environment import (
    DOCKER_DESKTOP_URL,
    EnvRetryWatcher,
    SystemInfo,
    can_launch_docker_desktop,
    format_environment_report,
    get_system_info,
    launch_docker_desktop,
)


class TestSystemInfo(unittest.TestCase):
    def test_display_format(self):
        info = SystemInfo(os_name="macOS", os_release="25.5.0", machine="arm64")
        self.assertEqual(info.display, "macOS 25.5.0 · arm64")

    def test_get_system_info_non_empty(self):
        info = get_system_info()
        self.assertTrue(info.os_name)
        self.assertTrue(info.os_release)
        self.assertTrue(info.machine)
        self.assertIn("·", info.display)


class TestFormatEnvironmentReport(unittest.TestCase):
    SYSTEM = SystemInfo(os_name="macOS", os_release="25.5.0", machine="arm64")

    def test_not_installed_report(self):
        report = format_environment_report(self.SYSTEM, DockerEnvStatus(False, False))
        self.assertIn("✗ 未安装", report)
        self.assertIn("Docker Desktop", report)
        self.assertIn("macOS 25.5.0 · arm64", report)

    def test_not_running_report(self):
        status = DockerEnvStatus(True, False, cli_version="27.3.1")
        report = format_environment_report(self.SYSTEM, status)
        self.assertIn("✗ 未运行", report)
        self.assertIn("27.3.1", report)
        self.assertIn("启动 Docker Desktop", report)

    def test_running_report(self):
        status = DockerEnvStatus(
            True, True, cli_version="27.3.1", server_version="27.3.1", host_platform="linux/arm64"
        )
        report = format_environment_report(self.SYSTEM, status)
        self.assertIn("✓ 运行中", report)
        self.assertIn("linux/arm64", report)
        self.assertNotIn("提示", report.split("✓")[0])  # 正常态无修复提示

    def test_report_uses_public_url(self):
        report = format_environment_report(self.SYSTEM, DockerEnvStatus(False, False))
        self.assertIn(DOCKER_DESKTOP_URL, report)


class TestLaunchDockerDesktop(unittest.TestCase):
    @patch("imageporter.core.environment.subprocess.Popen")
    @patch("imageporter.core.environment._platform.system", return_value="Darwin")
    def test_macos_opens_app(self, _, mock_popen):
        self.assertTrue(launch_docker_desktop())
        mock_popen.assert_called_once_with(["open", "-a", "Docker"])

    @patch("imageporter.core.environment.subprocess.Popen", side_effect=OSError("boom"))
    @patch("imageporter.core.environment._platform.system", return_value="Darwin")
    def test_launch_failure_returns_false(self, _, _popen):
        self.assertFalse(launch_docker_desktop())

    @patch("imageporter.core.environment.os")
    @patch("imageporter.core.environment._platform.system", return_value="Windows")
    def test_windows_startfile_known_path(self, _, mock_os):
        mock_os.path.exists.return_value = True
        self.assertTrue(launch_docker_desktop())
        mock_os.startfile.assert_called_once()

    @patch("imageporter.core.environment.os")
    @patch("imageporter.core.environment._platform.system", return_value="Windows")
    def test_windows_missing_exe_returns_false(self, _, mock_os):
        mock_os.path.exists.return_value = False
        self.assertFalse(launch_docker_desktop())

    @patch("imageporter.core.environment._platform.system", return_value="Linux")
    def test_linux_cannot_launch(self, _):
        self.assertFalse(launch_docker_desktop())
        self.assertFalse(can_launch_docker_desktop())

    @patch("imageporter.core.environment._platform.system", return_value="Darwin")
    def test_mac_can_launch(self, _):
        self.assertTrue(can_launch_docker_desktop())


class TestEnvRetryWatcher(unittest.TestCase):
    @staticmethod
    def _wait_until(condition, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return True
            time.sleep(0.005)
        return False

    def test_retries_until_running_then_stops(self):
        emitted: list[DockerEnvStatus] = []
        watcher = EnvRetryWatcher(
            emit_status=emitted.append,
            interval=0.01,
            sleeper=lambda seconds: None,  # 免真实等待
        )
        statuses = [
            DockerEnvStatus(True, False),
            DockerEnvStatus(True, False),
            DockerEnvStatus(True, True, server_version="27.0", host_platform="linux/arm64"),
        ]
        with patch(
            "imageporter.core.environment.probe_docker_environment", side_effect=statuses
        ):
            watcher.maybe_start(DockerEnvStatus(True, False))
            self.assertTrue(self._wait_until(lambda: not watcher.active))
        self.assertEqual([s.running for s in emitted], [False, False, True])
        self.assertFalse(watcher.active)

    def test_no_watch_when_running(self):
        emitted: list[DockerEnvStatus] = []
        watcher = EnvRetryWatcher(emit_status=emitted.append)
        watcher.maybe_start(DockerEnvStatus(True, True))
        self.assertFalse(watcher.active)
        self.assertEqual(emitted, [])

    def test_no_duplicate_watchers(self):
        watcher = EnvRetryWatcher(emit_status=lambda s: None, interval=0.05)
        # 模拟已有 watcher 在跑：再次 maybe_start 不应叠加
        watcher._active.set()
        with patch("imageporter.core.environment.probe_docker_environment") as mock_probe:
            watcher.maybe_start(DockerEnvStatus(True, False))
            mock_probe.assert_not_called()
        watcher._active.clear()


if __name__ == "__main__":
    unittest.main()
