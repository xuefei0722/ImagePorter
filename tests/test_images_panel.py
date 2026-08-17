"""Tests for imageporter.ui.images_panel — local image list, filter & selection."""

from __future__ import annotations

import unittest

from imageporter.core.docker import LocalImage
from imageporter.ui.images_panel import ImagesPanel


def make_images() -> list[LocalImage]:
    return [
        LocalImage("nginx", "latest", "abc123def456", "2 days ago", "104MB"),
        LocalImage("redis", "7", "def789abc123", "3 weeks ago", "138MB"),
        LocalImage("<none>", "<none>", "aaa111bbb222", "1 month ago", "52MB"),
    ]


class TestImagesPanel(unittest.TestCase):
    def setUp(self):
        self.refreshed = []
        self.delete_requests: list[list[str]] = []
        self.panel = ImagesPanel(
            on_refresh=lambda: self.refreshed.append(True),
            on_delete_selected=self.delete_requests.append,
        )

    def test_initial_empty_state(self):
        self.assertTrue(self.panel.empty_state.visible)
        self.assertFalse(self.panel.rows_view.visible)
        self.assertFalse(self.panel.delete_btn.visible)

    def test_refresh_renders_rows(self):
        self.panel.refresh(make_images())
        self.assertEqual(len(self.panel.rows_view.controls), 3)
        self.assertTrue(self.panel.rows_view.visible)
        self.assertEqual(self.panel.count_text.value, "3 个")

    def test_dangling_image_uses_id_ref(self):
        self.panel.refresh(make_images())
        # 第三行为悬空镜像：显示「无标签」且删除引用为短 ID
        row = self.panel.rows_view.controls[2].content
        title = row.controls[1].controls[0].value
        self.assertIn("无标签", title)
        row.controls[2].on_click("evt")  # 单个删除按钮
        self.assertEqual(self.delete_requests, [["aaa111bbb222"]])

    def test_search_filters_rows(self):
        self.panel.refresh(make_images())
        self.panel.search_input.value = "nginx"
        self.panel._render()
        self.assertEqual(len(self.panel.rows_view.controls), 1)
        self.assertEqual(self.panel.count_text.value, "1 / 3 个")

    def test_selection_updates_delete_button(self):
        self.panel.refresh(make_images())
        self.assertFalse(self.panel.delete_btn.visible)
        row = self.panel.rows_view.controls[0].content
        row.controls[0].on_change(_event_with_control(True))  # 勾选 nginx
        self.assertTrue(self.panel.delete_btn.visible)
        self.assertIn("1", self.panel.delete_btn.content)
        row.controls[0].on_change(_event_with_control(False))  # 取消勾选
        self.assertFalse(self.panel.delete_btn.visible)

    def test_delete_selected_sends_sorted_refs(self):
        self.panel.refresh(make_images())
        self.panel._selected = {"redis:7", "nginx:latest"}
        self.panel._sync_delete_btn()
        self.panel.delete_btn.on_click("evt")
        self.assertEqual(self.delete_requests, [["nginx:latest", "redis:7"]])

    def test_refresh_clears_selection(self):
        self.panel.refresh(make_images())
        self.panel._selected.add("nginx:latest")
        self.panel.refresh(make_images())
        self.assertFalse(self.panel._selected)
        self.assertFalse(self.panel.delete_btn.visible)

    def test_refresh_with_error_shows_hint(self):
        self.panel.refresh([], error="Cannot connect to the Docker daemon")
        self.assertTrue(self.panel.empty_state.visible)
        self.assertEqual(self.panel.count_text.value, "加载失败")
        hint = self.panel.empty_state.content.controls[1].value
        self.assertIn("加载失败", hint)

    def test_refresh_button_callback(self):
        self.panel.refresh_btn.on_click("evt")
        self.assertEqual(self.refreshed, [True])


def _event_with_control(value: bool):
    class _E:
        pass
    e = _E()
    e.control = type("C", (), {"value": value})()
    return e


if __name__ == "__main__":
    unittest.main()
