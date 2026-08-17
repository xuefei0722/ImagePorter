"""Tests for imageporter.ui.theme — theme construction."""

from __future__ import annotations

import unittest

import flet as ft

from imageporter.ui.theme import build_dark_theme, build_light_theme


class TestThemes(unittest.TestCase):
    def test_light_theme_colors(self):
        cs = build_light_theme().color_scheme
        self.assertEqual(cs.surface, "#FFFFFF")
        self.assertEqual(cs.primary, "#0066CC")
        self.assertEqual(cs.error, "#EF4444")
        self.assertEqual(cs.outline, "#CBD5E1")  # 对比度加深后的描边色

    def test_dark_theme_colors(self):
        cs = build_dark_theme().color_scheme
        self.assertEqual(cs.surface, "#0F172A")
        self.assertEqual(cs.primary, "#60A5FA")
        self.assertEqual(cs.error, "#F87171")
        self.assertEqual(cs.outline, "#475569")

    def test_visual_density_comfortable(self):
        self.assertEqual(build_light_theme().visual_density, ft.VisualDensity.COMFORTABLE)
        self.assertEqual(build_dark_theme().visual_density, ft.VisualDensity.COMFORTABLE)


if __name__ == "__main__":
    unittest.main()
