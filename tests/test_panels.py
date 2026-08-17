"""Tests for imageporter.ui.panels — headless panel construction and tab logic."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import flet as ft

from imageporter.ui.panels import build_main_panels


class TestMainPanels(unittest.TestCase):
    def setUp(self):
        self.panels = build_main_panels()

    def test_initial_state(self):
        self.assertEqual(self.panels.status_title.value, "准备就绪")
        self.assertEqual(self.panels.status_subtitle.value, "等待任务开始")
        self.assertTrue(self.panels.task_panel.visible)   # 默认显示任务列表
        self.assertFalse(self.panels.log_panel.visible)   # 默认隐藏日志

    def test_set_tab_visible_toggles_panels(self):
        self.assertTrue(self.panels.set_tab_visible(True))
        self.assertTrue(self.panels.log_panel.visible)
        self.assertFalse(self.panels.task_panel.visible)
        # 状态不变时返回 False（幂等）
        self.assertFalse(self.panels.set_tab_visible(True))

    def test_set_tab_visible_back_to_task(self):
        self.panels.set_tab_visible(True)
        self.assertTrue(self.panels.set_tab_visible(False))
        self.assertFalse(self.panels.log_panel.visible)
        self.assertTrue(self.panels.task_panel.visible)

    def test_switch_tab_internal_uses_schedule_update(self):
        page = MagicMock()
        self.panels.switch_tab(True, None, page)
        page.schedule_update.assert_called_once()

    def test_switch_tab_user_click_updates_controls(self):
        page = MagicMock()
        event = MagicMock()
        self.panels.switch_tab(True, event, page)  # 控件 update 为尽力而为，不应抛错
        self.assertTrue(self.panels.log_panel.visible)

    def test_switch_tab_no_change_skips_update(self):
        page = MagicMock()
        event = MagicMock()
        self.panels.switch_tab(False, event, page)  # 已处于任务页
        page.schedule_update.assert_not_called()

    def test_refresh_task_empty_state(self):
        # 初始：无任务 → 空状态可见
        self.panels.refresh_task_empty_state()
        self.assertFalse(self.panels.result_rows.visible)
        self.assertTrue(self.panels.task_empty_state.visible)
        # 加入任务行 → 列表可见
        self.panels.result_rows.controls.append(ft.Container())
        self.panels.refresh_task_empty_state()
        self.assertTrue(self.panels.result_rows.visible)
        self.assertFalse(self.panels.task_empty_state.visible)


if __name__ == "__main__":
    unittest.main()
