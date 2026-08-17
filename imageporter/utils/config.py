"""Configuration and preferences management."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import flet as ft

from imageporter.constants import CACHE_DIR, PREFS_FILE, WINDOW_HEIGHT, WINDOW_WIDTH


@dataclass(frozen=True)
class WindowState:
    """窗口状态记忆（最大化标志与非最大化时的尺寸）。"""

    maximized: bool = True  # 首次运行默认最大化
    width: int = WINDOW_WIDTH
    height: int = WINDOW_HEIGHT


def _read_prefs() -> dict:
    try:
        if not os.path.isfile(PREFS_FILE):
            return {}
        with open(PREFS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_prefs(data: dict) -> bool:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def load_theme_mode() -> ft.ThemeMode:
    """Load saved theme preference from prefs.json.

    Returns:
        ft.ThemeMode: The saved theme mode (LIGHT or DARK), defaults to LIGHT.
    """
    data = _read_prefs()
    mode = str(data.get("theme_mode", "light")).lower()
    return ft.ThemeMode.DARK if mode == "dark" else ft.ThemeMode.LIGHT


def save_theme_mode(mode: ft.ThemeMode) -> bool:
    """Save theme preference to prefs.json（读改写，保留其他偏好项）。"""
    data = _read_prefs()
    data["theme_mode"] = "dark" if mode == ft.ThemeMode.DARK else "light"
    return _write_prefs(data)


def load_window_state() -> WindowState:
    """读取记忆的窗口状态；无记录时返回默认（最大化 + 默认尺寸）。"""
    data = _read_prefs().get("window")
    if not isinstance(data, dict):
        return WindowState()
    try:
        return WindowState(
            maximized=bool(data.get("maximized", True)),
            width=max(600, int(data.get("width", WINDOW_WIDTH))),
            height=max(400, int(data.get("height", WINDOW_HEIGHT))),
        )
    except (TypeError, ValueError):
        return WindowState()


def save_window_state(state: WindowState) -> bool:
    """持久化窗口状态（读改写，保留其他偏好项）。"""
    data = _read_prefs()
    data["window"] = {
        "maximized": state.maximized,
        "width": state.width,
        "height": state.height,
    }
    return _write_prefs(data)
