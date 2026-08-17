"""Tests for imageporter.ui.env_bar — bottom environment status bar states."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import flet as ft

from imageporter.core.docker import DockerEnvStatus
from imageporter.core.environment import DOCKER_DESKTOP_URL, DOCKER_DOCS_URL, SystemInfo
from imageporter.ui.env_bar import EnvBar


def make_bar(**kwargs) -> EnvBar:
    defaults = dict(on_refresh=lambda e: None)
    defaults.update(kwargs)
    return EnvBar(**defaults)


class TestEnvBar(unittest.TestCase):
    def test_initial_state(self):
        bar = make_bar()
        self.assertEqual(bar.system_value.value, "检测中...")
        self.assertEqual(bar.docker_state.value, "检测中...")
        self.assertFalse(bar.action_btn.visible)
        self.assertIsInstance(bar.container, ft.Container)

    def test_set_system_info(self):
        bar = make_bar()
        bar.set_system_info(SystemInfo("Windows", "11", "AMD64"))
        self.assertEqual(bar.system_value.value, "Windows 11 · AMD64")
        self.assertIsNotNone(bar.system_value.tooltip)

    def test_docker_not_installed(self):
        bar = make_bar()
        bar.apply_docker_status(DockerEnvStatus(False, False))
        self.assertEqual(bar.docker_dot.color, "grey")
        self.assertEqual(bar.docker_state.value, "Docker 未安装")
        self.assertEqual(bar.docker_state.color, "onSurfaceVariant")

    def test_docker_not_running(self):
        bar = make_bar()
        with patch("imageporter.ui.env_bar.can_launch_docker_desktop", return_value=False):
            bar.apply_docker_status(DockerEnvStatus(True, False, cli_version="27.3.1"))
        self.assertEqual(bar.docker_dot.color, "red")
        self.assertEqual(bar.docker_state.value, "Docker 未运行")
        self.assertEqual(bar.docker_state.color, "red")
        self.assertIn("未响应", bar.docker_detail.value)
        self.assertIn("27.3.1", bar.container.tooltip)

    def test_docker_running(self):
        bar = make_bar()
        bar.apply_docker_status(
            DockerEnvStatus(
                True, True,
                cli_version="29.7.2", server_version="29.7.2",
                host_platform="linux/arm64",
            )
        )
        self.assertEqual(bar.docker_dot.color, "green")
        self.assertEqual(bar.docker_state.value, "Docker 运行中")
        self.assertEqual(bar.docker_detail.value, "29.7.2 · 引擎 linux/arm64")
        self.assertIn("Linux 虚拟机", bar.container.tooltip)


class TestEnvBarActions(unittest.TestCase):
    def test_not_installed_shows_download_link(self):
        bar = make_bar()
        bar.apply_docker_status(DockerEnvStatus(False, False))
        self.assertTrue(bar.action_btn.visible)
        self.assertEqual(bar.action_btn.url, DOCKER_DESKTOP_URL)
        self.assertIn("获取 Docker Desktop", bar.action_btn.content)

    def test_not_running_with_launcher_shows_launch_button(self):
        launched = []
        bar = make_bar(on_launch=lambda e: launched.append(e))
        with patch("imageporter.ui.env_bar.can_launch_docker_desktop", return_value=True):
            bar.apply_docker_status(DockerEnvStatus(True, False))
        self.assertTrue(bar.action_btn.visible)
        self.assertIn("启动 Docker Desktop", bar.action_btn.content)
        self.assertIsNone(bar.action_btn.url)
        bar.action_btn.on_click("evt")
        self.assertEqual(launched, ["evt"])

    def test_not_running_without_launcher_shows_docs_link(self):
        bar = make_bar(on_launch=lambda e: None)
        with patch("imageporter.ui.env_bar.can_launch_docker_desktop", return_value=False):
            bar.apply_docker_status(DockerEnvStatus(True, False))
        self.assertTrue(bar.action_btn.visible)
        self.assertEqual(bar.action_btn.url, DOCKER_DOCS_URL)
        self.assertIn("文档", bar.action_btn.content)

    def test_running_hides_action(self):
        bar = make_bar(on_launch=lambda e: None)
        with patch("imageporter.ui.env_bar.can_launch_docker_desktop", return_value=True):
            bar.apply_docker_status(DockerEnvStatus(True, True))
        self.assertFalse(bar.action_btn.visible)

    def test_set_waiting_launch(self):
        bar = make_bar()
        bar.set_waiting_launch()
        self.assertIn("等待守护进程就绪", bar.docker_detail.value)
        self.assertFalse(bar.action_btn.visible)

    def test_refresh_callback_wired(self):
        clicked = []
        bar = EnvBar(on_refresh=lambda e: clicked.append(e))
        # 刷新按钮是状态栏行内最后一个控件
        bar.refresh_btn.on_click("evt")
        self.assertEqual(clicked, ["evt"])


if __name__ == "__main__":
    unittest.main()
