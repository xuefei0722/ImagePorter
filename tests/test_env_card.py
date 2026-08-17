"""Tests for imageporter.ui.env_card — environment status card states."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import flet as ft

from imageporter.core.docker import DockerEnvStatus
from imageporter.core.environment import DOCKER_DESKTOP_URL, DOCKER_DOCS_URL, SystemInfo
from imageporter.ui.env_card import EnvironmentCard


def make_card(**kwargs) -> EnvironmentCard:
    defaults = dict(on_refresh=lambda e: None)
    defaults.update(kwargs)
    return EnvironmentCard(**defaults)


class TestEnvironmentCard(unittest.TestCase):
    def test_initial_state(self):
        card = make_card()
        self.assertEqual(card.system_value.value, "检测中...")
        self.assertEqual(card.docker_state.value, "检测中...")
        self.assertFalse(card.action_btn.visible)
        self.assertIsInstance(card.container, ft.Container)

    def test_set_system_info(self):
        card = make_card()
        card.set_system_info(SystemInfo("Windows", "11", "AMD64"))
        self.assertEqual(card.system_value.value, "Windows 11 · AMD64")
        self.assertIsNotNone(card.system_value.tooltip)

    def test_docker_not_installed(self):
        card = make_card()
        card.apply_docker_status(DockerEnvStatus(False, False))
        self.assertEqual(card.docker_dot.color, "grey")
        self.assertEqual(card.docker_state.value, "Docker 未安装")
        self.assertEqual(card.docker_state.color, "onSurfaceVariant")

    def test_docker_not_running(self):
        card = make_card()
        with patch("imageporter.ui.env_card.can_launch_docker_desktop", return_value=False):
            card.apply_docker_status(DockerEnvStatus(True, False, cli_version="27.3.1"))
        self.assertEqual(card.docker_dot.color, "red")
        self.assertEqual(card.docker_state.value, "Docker 未运行")
        self.assertEqual(card.docker_state.color, "red")
        self.assertIn("27.3.1", card.container.tooltip)

    def test_docker_running(self):
        card = make_card()
        card.apply_docker_status(
            DockerEnvStatus(
                True, True,
                cli_version="29.7.2", server_version="29.7.2",
                host_platform="linux/aarch64",
            )
        )
        self.assertEqual(card.docker_dot.color, "green")
        self.assertEqual(card.docker_state.value, "Docker 运行中")
        self.assertEqual(card.docker_state.color, "green")
        self.assertEqual(card.docker_detail.value, "服务端 29.7.2 · 主机 linux/aarch64")
        self.assertEqual(card.container.tooltip, "Docker CLI 29.7.2")


class TestEnvironmentCardActions(unittest.TestCase):
    def test_not_installed_shows_download_link(self):
        card = make_card()
        card.apply_docker_status(DockerEnvStatus(False, False))
        self.assertTrue(card.action_btn.visible)
        self.assertEqual(card.action_btn.url, DOCKER_DESKTOP_URL)
        self.assertIn("获取 Docker Desktop", card.action_btn.content)

    def test_not_running_with_launcher_shows_launch_button(self):
        launched = []
        card = make_card(on_launch=lambda e: launched.append(e))
        with patch("imageporter.ui.env_card.can_launch_docker_desktop", return_value=True):
            card.apply_docker_status(DockerEnvStatus(True, False))
        self.assertTrue(card.action_btn.visible)
        self.assertIn("启动 Docker Desktop", card.action_btn.content)
        self.assertIsNone(card.action_btn.url)
        card.action_btn.on_click("evt")
        self.assertEqual(launched, ["evt"])

    def test_not_running_without_launcher_shows_docs_link(self):
        card = make_card(on_launch=lambda e: None)
        with patch("imageporter.ui.env_card.can_launch_docker_desktop", return_value=False):
            card.apply_docker_status(DockerEnvStatus(True, False))
        self.assertTrue(card.action_btn.visible)
        self.assertEqual(card.action_btn.url, DOCKER_DOCS_URL)
        self.assertIn("文档", card.action_btn.content)

    def test_running_hides_action(self):
        card = make_card(on_launch=lambda e: None)
        with patch("imageporter.ui.env_card.can_launch_docker_desktop", return_value=True):
            card.apply_docker_status(DockerEnvStatus(True, True))
        self.assertFalse(card.action_btn.visible)

    def test_set_waiting_launch(self):
        card = make_card()
        card.set_waiting_launch()
        self.assertIn("等待守护进程就绪", card.docker_detail.value)
        self.assertFalse(card.action_btn.visible)

    def test_refresh_callback_wired(self):
        clicked = []
        card = EnvironmentCard(on_refresh=lambda e: clicked.append(e))
        header_row = card.container.content.controls[0]
        header_row.controls[1].on_click("evt")
        self.assertEqual(clicked, ["evt"])


if __name__ == "__main__":
    unittest.main()
