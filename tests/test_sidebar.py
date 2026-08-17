"""Tests for imageporter.ui.sidebar — headless sidebar construction."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import flet as ft

from imageporter.constants import PLATFORM_OPTIONS
from imageporter.ui.sidebar import (
    build_button_content,
    build_sidebar,
    build_start_button,
    refresh_arch_chip_styles,
)


def make_page() -> MagicMock:
    page = MagicMock()
    page.theme_mode = ft.ThemeMode.LIGHT
    return page


class TestBuildSidebar(unittest.TestCase):
    def setUp(self):
        self.page = make_page()
        theme_btn = ft.IconButton(icon=ft.Icons.DARK_MODE)
        start_btn = build_start_button(lambda e: None)
        self.sidebar = build_sidebar(
            self.page, theme_btn, start_btn, ft.Container(),
            on_about_click=lambda e: None,
            on_arch_help_click=lambda e: None,
        )

    def test_all_platform_chips_built(self):
        self.assertEqual(set(self.sidebar.arch_containers.keys()), set(PLATFORM_OPTIONS))

    def test_default_selection_is_amd64(self):
        self.assertEqual(self.sidebar.selected_platforms(), ["linux/amd64"])

    def test_chip_click_toggles_selection(self):
        chip = self.sidebar.arch_containers["linux/arm64"]
        event = MagicMock()
        event.control = chip
        chip.on_click(event)
        self.assertIn("linux/arm64", self.sidebar.selected_platforms())
        chip.on_click(event)
        self.assertNotIn("linux/arm64", self.sidebar.selected_platforms())

    def test_selected_chip_style_light_vs_dark(self):
        chip = self.sidebar.arch_containers["linux/amd64"]
        self.assertEqual(chip.bgcolor, "#E6F0FF")  # 浅色选中态
        self.page.theme_mode = ft.ThemeMode.DARK
        refresh_arch_chip_styles(self.page, self.sidebar.arch_containers)
        self.assertEqual(chip.bgcolor, "#1E3A5F")  # 深色选中态

    def test_output_dir_defaults_to_downloads(self):
        self.assertTrue(self.sidebar.output_input.value.endswith("Downloads"))

    def test_concurrency_and_cleanup_defaults(self):
        self.assertEqual(self.sidebar.concurrency_text.value, "3")
        self.assertTrue(self.sidebar.cleanup_switch.value)

    def test_images_input_is_multiline(self):
        self.assertTrue(self.sidebar.images_input.multiline)

    def test_container_is_flet_container(self):
        self.assertIsInstance(self.sidebar.container, ft.Container)

    def test_dir_picker_registered_on_page(self):
        self.page.services.append.assert_called_once()


class TestStartButton(unittest.TestCase):
    def test_build_returns_container_with_button(self):
        btn = build_start_button(lambda e: None)
        self.assertIsInstance(btn, ft.Container)
        self.assertIsInstance(btn.content, ft.Button)
        self.assertIsNotNone(btn.content.on_click)

    def test_button_content_row(self):
        row = build_button_content("开始执行", ft.Icons.ROCKET_LAUNCH_ROUNDED)
        self.assertIsInstance(row, ft.Row)
        self.assertEqual(len(row.controls), 2)


if __name__ == "__main__":
    unittest.main()
