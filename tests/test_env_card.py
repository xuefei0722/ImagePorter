"""Tests for imageporter.ui.env_card — environment status card states."""

from __future__ import annotations

import unittest

import flet as ft

from imageporter.core.docker import DockerEnvStatus
from imageporter.core.environment import SystemInfo
from imageporter.ui.env_card import EnvironmentCard


def make_card() -> EnvironmentCard:
    return EnvironmentCard(on_refresh=lambda e: None)


class TestEnvironmentCard(unittest.TestCase):
    def test_initial_state(self):
        card = make_card()
        self.assertEqual(card.system_value.value, "检测中...")
        self.assertEqual(card.docker_state.value, "检测中...")
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
        self.assertIn("安装", card.docker_detail.value)

    def test_docker_not_running(self):
        card = make_card()
        card.apply_docker_status(DockerEnvStatus(True, False, cli_version="27.3.1"))
        self.assertEqual(card.docker_dot.color, "red")
        self.assertEqual(card.docker_state.value, "Docker 未运行")
        self.assertEqual(card.docker_state.color, "red")
        self.assertIn("启动", card.docker_detail.value)
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

    def test_refresh_callback_wired(self):
        clicked = []
        card = EnvironmentCard(on_refresh=lambda e: clicked.append(e))
        # 刷新按钮位于标题行内，点击应触发回调
        header_row = card.container.content.controls[0]
        refresh_btn = header_row.controls[1]
        refresh_btn.on_click("evt")
        self.assertEqual(clicked, ["evt"])


if __name__ == "__main__":
    unittest.main()
