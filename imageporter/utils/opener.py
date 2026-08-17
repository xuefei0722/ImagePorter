"""跨平台「在文件管理器中显示」工具。"""

from __future__ import annotations

import os
import platform as _platform_mod
import subprocess


def reveal_in_file_manager(path: str) -> None:
    """在系统文件管理器中定位文件（尽力而为，失败静默）。"""
    try:
        system = _platform_mod.system()
        if system == "Darwin":
            subprocess.Popen(["open", "-R", path])
        elif system == "Windows":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:  # Linux / 其他
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
    except Exception:
        pass
