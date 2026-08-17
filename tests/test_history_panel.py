"""Tests for imageporter.ui.history_panel — history list rendering & callbacks."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from imageporter.ui.history_panel import HistoryPanel
from imageporter.utils.history import ExportRecord


def make_record(n: int, path: str = "/tmp/out.tar") -> ExportRecord:
    return ExportRecord(
        timestamp=f"2026-08-17T12:00:{n:02d}",
        image=f"nginx{n}",
        platform="linux/amd64",
        tar_path=path,
        file_size=2048,
    )


class TestHistoryPanel(unittest.TestCase):
    def setUp(self):
        self.opened: list[str] = []
        self.deleted: list[str] = []
        self.cleared = []
        self.panel = HistoryPanel(
            on_open=self.opened.append,
            on_delete=self.deleted.append,
            on_clear_all=lambda: self.cleared.append(True),
        )

    def test_initial_empty_state(self):
        self.assertTrue(self.panel.empty_state.visible)
        self.assertFalse(self.panel.rows_view.visible)
        self.assertEqual(self.panel.count_text.value, "0 条")
        self.assertFalse(self.panel.clear_btn.visible)

    def test_refresh_renders_rows(self):
        self.panel.refresh([make_record(1), make_record(2)])
        self.assertEqual(len(self.panel.rows_view.controls), 2)
        self.assertTrue(self.panel.rows_view.visible)
        self.assertFalse(self.panel.empty_state.visible)
        self.assertEqual(self.panel.count_text.value, "2 条")
        self.assertTrue(self.panel.clear_btn.visible)

    def test_missing_file_hint(self):
        with patch("imageporter.ui.history_panel.os.path.exists", return_value=False):
            self.panel.refresh([make_record(1)])
        row_text = str(self.panel.rows_view.controls[0].content.controls[1].controls[1].value)
        self.assertIn("文件已不在磁盘", row_text)

    def test_open_callback_fires_with_path(self):
        self.panel.refresh([make_record(1, path="/tmp/a.tar")])
        row = self.panel.rows_view.controls[0].content
        row.controls[2].on_click("evt")  # 打开按钮
        self.assertEqual(self.opened, ["/tmp/a.tar"])

    def test_delete_callback_fires_with_key(self):
        record = make_record(1)
        self.panel.refresh([record])
        row = self.panel.rows_view.controls[0].content
        row.controls[3].on_click("evt")  # 删除按钮
        self.assertEqual(self.deleted, [record.key])

    def test_clear_all_callback(self):
        self.panel.clear_btn.on_click("evt")
        self.assertEqual(self.cleared, [True])

    def test_refresh_empty_hides_rows(self):
        self.panel.refresh([make_record(1)])
        self.panel.refresh([])
        self.assertTrue(self.panel.empty_state.visible)


if __name__ == "__main__":
    unittest.main()
