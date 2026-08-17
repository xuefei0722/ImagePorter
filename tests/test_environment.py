"""Tests for imageporter.core.environment — system info & check report."""

from __future__ import annotations

import unittest

from imageporter.core.docker import DockerEnvStatus
from imageporter.core.environment import (
    SystemInfo,
    format_environment_report,
    get_system_info,
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


if __name__ == "__main__":
    unittest.main()
