"""明暗主题构建：更清爽的蓝白灰配色。"""

from __future__ import annotations

import flet as ft


def build_light_theme() -> ft.Theme:
    """浅色主题（蓝白灰）。"""
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            surface="#FFFFFF",
            on_surface="#333333",
            on_surface_variant="#64748B",
            outline="#CBD5E1",           # 从 #E2E8F0 加深，对比度 ~1.8:1 → ~2.5:1
            primary="#0066CC",
            error="#EF4444",
        ),
        visual_density=ft.VisualDensity.COMFORTABLE,
    )


def build_dark_theme() -> ft.Theme:
    """深色主题（深蓝灰）。"""
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            surface="#0F172A",
            on_surface="#E2E8F0",
            on_surface_variant="#94A3B8",
            outline="#475569",           # 从 #334155 加亮，对比度 ~1.8:1 → ~3.0:1
            primary="#60A5FA",
            error="#F87171",
        ),
        visual_density=ft.VisualDensity.COMFORTABLE,
    )
