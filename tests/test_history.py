"""Tests for imageporter.utils.history — export history persistence."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from imageporter.constants import HISTORY_LIMIT
from imageporter.utils import history
from imageporter.utils.history import ExportRecord, human_file_size


def make_record(n: int = 0, path: str = "/tmp/out.tar") -> ExportRecord:
    return ExportRecord(
        timestamp=f"2026-08-17T12:00:{n:02d}",
        image=f"nginx{n}",
        platform="linux/amd64",
        tar_path=path,
        file_size=1024,
    )


class HistoryFileTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cache_dir = os.path.join(tmp.name, "cache")
        self.history_file = os.path.join(self.cache_dir, "history.json")
        self.patchers = [
            patch.object(history, "HISTORY_FILE", self.history_file),
            patch.object(history, "CACHE_DIR", self.cache_dir),
        ]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)


class TestHumanFileSize(unittest.TestCase):
    def test_units(self):
        cases = {0: "0B", 512: "512B", 2048: "2.0KB", 5 * 1024 * 1024: "5.0MB", 3 * 1024**3: "3.0GB"}
        for size, expected in cases.items():
            self.assertEqual(human_file_size(size), expected, size)


class TestHistoryStore(HistoryFileTestCase):
    def test_missing_file_returns_empty(self):
        self.assertEqual(history.load_history(), [])

    def test_add_and_load_roundtrip_newest_first(self):
        history.add_record(make_record(1))
        history.add_record(make_record(2))
        records = history.load_history()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].image, "nginx2")  # 新记录在前

    def test_add_caps_limit(self):
        for i in range(HISTORY_LIMIT + 20):
            history.add_record(make_record(i))
        records = history.load_history()
        self.assertEqual(len(records), HISTORY_LIMIT)
        self.assertEqual(records[0].image, f"nginx{HISTORY_LIMIT + 19}")  # 最新的保留

    def test_remove_record_by_key(self):
        history.add_record(make_record(1, path="/tmp/a.tar"))
        history.add_record(make_record(2, path="/tmp/b.tar"))
        target = history.load_history()[1]  # 旧的那条
        records = history.remove_record(target.key)
        self.assertEqual([r.tar_path for r in records], ["/tmp/b.tar"])

    def test_clear_history(self):
        history.add_record(make_record())
        history.clear_history()
        self.assertEqual(history.load_history(), [])

    def test_corrupt_file_returns_empty(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self.history_file, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(history.load_history(), [])

    def test_corrupt_entries_skipped(self):
        import json
        os.makedirs(self.cache_dir, exist_ok=True)
        payload = [
            {"timestamp": "t", "image": "ok", "platform": "p", "tar_path": "/x.tar", "file_size": 1},
            {"broken": "entry"},
        ]
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        records = history.load_history()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].image, "ok")

    def test_record_key(self):
        rec = make_record()
        self.assertEqual(rec.key, f"{rec.timestamp}|{rec.tar_path}")


if __name__ == "__main__":
    unittest.main()
