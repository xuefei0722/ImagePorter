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


if __name__ == "__main__":
    unittest.main()
