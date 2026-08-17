"""Tests for imageporter.ui.dialogs — dialog construction with a mocked page."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import flet as ft

from imageporter import __version__
from imageporter.constants import ARCH_REFERENCE_ROWS
from imageporter.ui.dialogs import build_about_dialog, build_arch_help_dialog, open_dialog


def collect_texts(ctrl) -> list[str]:
    """递归遍历 Flet 控件树，收集所有 ft.Text 的文本值。"""
    texts: list[str] = []
    if isinstance(ctrl, ft.Text):
        texts.append(str(ctrl.value or ""))
    for attr in ("content", "title", "label"):
        child = getattr(ctrl, attr, None)
        if isinstance(child, (ft.Control, str)):
            if isinstance(child, str):
                texts.append(child)
            else:
                texts.extend(collect_texts(child))
    for child in getattr(ctrl, "controls", None) or []:
        texts.extend(collect_texts(child))
    for child in getattr(ctrl, "actions", None) or []:
        texts.extend(collect_texts(child))
    return texts


class TestArchHelpDialog(unittest.TestCase):
    def test_build_returns_alert_dialog(self):
        dialog = build_arch_help_dialog(MagicMock())
        self.assertIsInstance(dialog, ft.AlertDialog)

    def test_contains_all_platform_reference_rows(self):
        dialog = build_arch_help_dialog(MagicMock())
        joined = "\n".join(collect_texts(dialog))
        for platform, _, _ in ARCH_REFERENCE_ROWS:
            self.assertIn(platform, joined)


class TestAboutDialog(unittest.TestCase):
    def test_build_returns_alert_dialog(self):
        dialog = build_about_dialog(MagicMock())
        self.assertIsInstance(dialog, ft.AlertDialog)

    def test_version_single_source(self):
        """M-7：关于对话框版本号必须来自 __version__ 单一来源。"""
        dialog = build_about_dialog(MagicMock())
        joined = "\n".join(collect_texts(dialog))
        self.assertIn(f"版本: v{__version__}", joined)
        self.assertIn("MIT License", joined)


class TestOpenDialog(unittest.TestCase):
    def test_open_appends_to_overlay_and_sets_flag(self):
        page = MagicMock()
        page.overlay = []
        dialog = MagicMock()
        open_dialog(page, dialog, "错误提示")
        self.assertIn(dialog, page.overlay)
        self.assertTrue(dialog.open)
        page.update.assert_called_once()

    def test_open_failure_shows_snackbar_via_overlay(self):
        """flet 0.81：SnackBar 提示须通过 overlay 挂载（无 page.snack_bar 属性）。"""
        page = MagicMock()
        page.overlay = MagicMock()
        page.overlay.append.side_effect = [RuntimeError("boom"), None]  # 首次挂载失败，SnackBar 成功
        dialog = MagicMock()
        open_dialog(page, dialog, "错误提示")
        page.update.assert_called()
        self.assertEqual(page.overlay.append.call_count, 2)
        snackbar = page.overlay.append.call_args_list[1].args[0]
        self.assertIsInstance(snackbar, ft.SnackBar)
        self.assertTrue(snackbar.open)


class TestConfirmDialog(unittest.TestCase):
    def test_confirm_runs_callback_and_closes(self):
        from imageporter.ui.dialogs import build_confirm_dialog

        page = MagicMock()
        confirmed = []
        dialog = build_confirm_dialog(
            page, "删除确认", "将删除 2 个镜像，不可恢复", "删除",
            lambda: confirmed.append(True),
        )
        self.assertIsInstance(dialog, ft.AlertDialog)
        # actions: [取消, 确认]
        cancel_btn, confirm_btn = dialog.actions
        confirm_btn.on_click("evt")
        self.assertEqual(confirmed, [True])
        self.assertFalse(dialog.open)  # 确认后关闭
        page.update.assert_called()

    def test_cancel_skips_callback(self):
        from imageporter.ui.dialogs import build_confirm_dialog

        page = MagicMock()
        confirmed = []
        dialog = build_confirm_dialog(page, "确认", "消息", "确定", lambda: confirmed.append(True))
        cancel_btn = dialog.actions[0]
        cancel_btn.on_click("evt")
        self.assertEqual(confirmed, [])
        self.assertFalse(dialog.open)


if __name__ == "__main__":
    unittest.main()
