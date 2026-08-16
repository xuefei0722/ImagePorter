"""Configuration and preferences management."""

from __future__ import annotations

import json
import os

import flet as ft

from imageporter.constants import CACHE_DIR, PREFS_FILE


def load_theme_mode() -> ft.ThemeMode:
    """Load saved theme preference from prefs.json.

    Returns:
        ft.ThemeMode: The saved theme mode (LIGHT or DARK), defaults to LIGHT.
    """
    try:
        if not os.path.isfile(PREFS_FILE):
            return ft.ThemeMode.LIGHT
        with open(PREFS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        mode = str(data.get("theme_mode", "light")).lower()
        return ft.ThemeMode.DARK if mode == "dark" else ft.ThemeMode.LIGHT
    except Exception:
        return ft.ThemeMode.LIGHT


def save_theme_mode(mode: ft.ThemeMode) -> bool:
    """Save theme preference to prefs.json.

    Args:
        mode (ft.ThemeMode): The theme mode to save (LIGHT or DARK).

    Returns:
        bool: True if persisted successfully; False otherwise（调用方可据此提示用户）。
    """
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        payload = {"theme_mode": "dark" if mode == ft.ThemeMode.DARK else "light"}
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        return True
    except Exception:
        return False
