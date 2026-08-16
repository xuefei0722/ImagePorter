"""Tests for imageporter.ui.task_row — headless control state transitions.

Flet 控件在未挂载页面前是普通 Python 对象，可无窗口断言状态迁移。
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import flet as ft

from imageporter.ui.task_row import TaskRow


class TestTaskRow(unittest.TestCase):
    def setUp(self):
        self.row = TaskRow("nginx", "linux/amd64")

    def test_initial_state(self):
        self.assertFalse(self.row.is_success)
        self.assertIsNone(self.row.final_path)
        self.assertEqual(self.row.text_pull.value, "等待拉取")
        self.assertEqual(self.row.text_save.value, "等待导出")
        self.assertEqual(self.row.image_name, "nginx")
        self.assertEqual(self.row.platform, "linux/amd64")

    def test_update_pull_running_shows_progress(self):
        self.row.update_pull("拉取中...")
        self.assertEqual(self.row.icon_ctrl.icon, ft.Icons.RADIO_BUTTON_CHECKED)
        self.assertEqual(self.row.icon_ctrl.color, "primary")
        self.assertIsInstance(self.row.pull_icon_container.content, ft.ProgressRing)

    def test_update_pull_success(self):
        self.row.update_pull("拉取完成", ok=True)
        self.assertEqual(self.row.text_pull.color, "green")
        self.assertEqual(self.row.pull_icon_container.content.icon, ft.Icons.DOWNLOAD_DONE)

    def test_update_pull_failure(self):
        self.row.update_pull("失败", ok=False)
        self.assertEqual(self.row.text_pull.color, "red")
        self.assertEqual(self.row.pull_icon_container.content.icon, ft.Icons.ERROR_OUTLINE)

    def test_update_pull_progress(self):
        self.row.update_pull_progress(3, 7)
        self.assertEqual(self.row.text_pull.value, "3/7 层")
        self.assertEqual(self.row.text_pull.color, "primary")

    def test_update_pull_progress_zero_total_keeps_status(self):
        self.row.update_pull("拉取中...")
        self.row.update_pull_progress(0, 0)
        self.assertEqual(self.row.text_pull.value, "拉取中...")

    def test_update_save_success_sets_path(self):
        tar = "/tmp/nginx_latest_linux_amd64.tar"
        self.row.update_save("导出完成", ok=True, path=tar)
        self.assertEqual(self.row.final_path, tar)
        self.assertEqual(self.row.text_path.value, "nginx_latest_linux_amd64.tar")
        self.assertIsNotNone(self.row.path_container.on_click)
        self.assertEqual(self.row.text_save.color, "green")
        self.assertEqual(self.row.save_icon_container.content.icon, ft.Icons.CHECK_CIRCLE)

    def test_update_save_in_progress_shows_ring(self):
        self.row.update_save("导出中...")
        self.assertIsInstance(self.row.save_icon_container.content, ft.ProgressRing)

    def test_update_save_failure(self):
        self.row.update_save("失败", ok=False)
        self.assertEqual(self.row.text_save.color, "red")

    def test_complete_success(self):
        self.row.complete(True)
        self.assertTrue(self.row.is_success)
        self.assertEqual(self.row.icon_ctrl.icon, ft.Icons.CHECK_CIRCLE)
        self.assertEqual(self.row.icon_ctrl.color, "green")

    def test_complete_failure(self):
        self.row.complete(False)
        self.assertFalse(self.row.is_success)
        self.assertEqual(self.row.icon_ctrl.icon, ft.Icons.ERROR)
        self.assertEqual(self.row.icon_ctrl.color, "red")

    def test_hover_path_enter_and_leave(self):
        enter = MagicMock()
        enter.data = "true"
        self.row._hover_path(enter)
        self.assertEqual(self.row.text_path.style.decoration, ft.TextDecoration.UNDERLINE)
        self.assertEqual(self.row.text_path.color, "primary")

        leave = MagicMock()
        leave.data = "false"
        self.row._hover_path(leave)
        self.assertEqual(self.row.text_path.style.decoration, ft.TextDecoration.NONE)
        self.assertEqual(self.row.text_path.color, "grey")

    def test_open_path_without_existing_file_does_nothing(self):
        with patch("imageporter.ui.task_row.subprocess.Popen") as popen:
            self.row._open_path(MagicMock())  # final_path 为 None
            popen.assert_not_called()

    def test_open_path_darwin_reveals_in_finder(self):
        self.row.final_path = "/tmp/x.tar"
        with patch("imageporter.ui.task_row.os.path.exists", return_value=True), \
             patch("imageporter.ui.task_row._platform_mod.system", return_value="Darwin"), \
             patch("imageporter.ui.task_row.subprocess.Popen") as popen:
            self.row._open_path(MagicMock())
            popen.assert_called_once_with(["open", "-R", "/tmp/x.tar"])


if __name__ == "__main__":
    unittest.main()
