"""Tests for imageporter.utils.config — preferences persistence."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import flet as ft

from imageporter.utils import config


class ThemePrefsTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cache_dir = os.path.join(tmp.name, "cache")
        self.prefs = os.path.join(self.cache_dir, "prefs.json")

    def test_load_missing_file_defaults_light(self):
        with patch.object(config, "PREFS_FILE", self.prefs):
            self.assertEqual(config.load_theme_mode(), ft.ThemeMode.LIGHT)

    def test_save_dark_then_load_roundtrip(self):
        with patch.object(config, "PREFS_FILE", self.prefs), \
             patch.object(config, "CACHE_DIR", self.cache_dir):
            self.assertTrue(config.save_theme_mode(ft.ThemeMode.DARK))
            self.assertEqual(config.load_theme_mode(), ft.ThemeMode.DARK)
        with open(self.prefs, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["theme_mode"], "dark")

    def test_save_light_roundtrip(self):
        with patch.object(config, "PREFS_FILE", self.prefs), \
             patch.object(config, "CACHE_DIR", self.cache_dir):
            self.assertTrue(config.save_theme_mode(ft.ThemeMode.LIGHT))
            self.assertEqual(config.load_theme_mode(), ft.ThemeMode.LIGHT)

    def test_load_corrupt_file_defaults_light(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self.prefs, "w", encoding="utf-8") as f:
            f.write("{not json")
        with patch.object(config, "PREFS_FILE", self.prefs):
            self.assertEqual(config.load_theme_mode(), ft.ThemeMode.LIGHT)

    def test_save_failure_returns_false(self):
        """M-4：持久化失败必须可被调用方感知（返回 False）。"""
        # PREFS_FILE 指向一个目录路径：open() 目录必然失败
        with patch.object(config, "PREFS_FILE", self.cache_dir), \
             patch.object(config, "CACHE_DIR", self.cache_dir):
            self.assertFalse(config.save_theme_mode(ft.ThemeMode.DARK))


class WindowStateTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cache_dir = os.path.join(tmp.name, "cache")
        self.prefs = os.path.join(self.cache_dir, "prefs.json")
        self.patchers = [
            patch.object(config, "PREFS_FILE", self.prefs),
            patch.object(config, "CACHE_DIR", self.cache_dir),
        ]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_default_first_launch_maximized(self):
        state = config.load_window_state()
        self.assertTrue(state.maximized)

    def test_roundtrip(self):
        state = config.WindowState(maximized=False, width=1440, height=900)
        self.assertTrue(config.save_window_state(state))
        loaded = config.load_window_state()
        self.assertEqual(
            (loaded.maximized, loaded.width, loaded.height), (False, 1440, 900)
        )

    def test_theme_and_window_coexist(self):
        """窗口状态保存不得覆盖主题偏好（读改写语义）。"""
        self.assertTrue(config.save_theme_mode(ft.ThemeMode.DARK))
        self.assertTrue(
            config.save_window_state(config.WindowState(maximized=False, width=1024, height=768))
        )
        self.assertEqual(config.load_theme_mode(), ft.ThemeMode.DARK)
        self.assertFalse(config.load_window_state().maximized)

    def test_corrupt_window_entry_falls_back(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self.prefs, "w", encoding="utf-8") as f:
            f.write('{"window": {"maximized": "yes", "width": "bad"}}')
        state = config.load_window_state()
        self.assertTrue(state.maximized)  # 解析失败回退默认

    def test_undersized_clamped(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self.prefs, "w", encoding="utf-8") as f:
            f.write('{"window": {"maximized": false, "width": 100, "height": 50}}')
        state = config.load_window_state()
        self.assertGreaterEqual(state.width, 600)
        self.assertGreaterEqual(state.height, 400)


if __name__ == "__main__":
    unittest.main()
