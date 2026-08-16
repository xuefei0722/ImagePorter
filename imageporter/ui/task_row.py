"""
TaskRow UI component for displaying image pull and export status.

控件刷新由 main.py 的 ui_pump 事件循环统一批处理，
本组件只做状态变更，不直接触发整页刷新。
"""

from __future__ import annotations

import os
import platform as _platform_mod
import subprocess

import flet as ft


class TaskRow(ft.Container):
    """UI component representing a single image pull/export task row.

    Displays the image name, platform, pull status with progress, export status,
    and final file path with file manager integration.
    """

    def __init__(self, image: str, platform: str):
        # 注意：ft.Container 自带 image（背景装饰）字段，会覆盖同名实例属性，
        # 因此镜像名使用 image_name 避免冲突
        self.image_name = image
        self.platform = platform
        self.is_success = False
        self.final_path: str | None = None

        # 使用更简洁的图标和字体
        self.icon_ctrl = ft.Icon(ft.Icons.CIRCLE_OUTLINED, color="grey_400", size=20)

        self.text_pull = ft.Text("等待拉取", size=12, width=100, color="grey")
        self.text_save = ft.Text("等待导出", size=12, width=100, color="grey")

        self.pull_icon_container = ft.Container(
            content=ft.Icon(ft.Icons.DOWNLOAD, size=12, color="grey"),
            width=12,
            height=12,
            alignment=ft.Alignment(0, 0),
        )
        self.save_icon_container = ft.Container(
            content=ft.Icon(ft.Icons.SAVE, size=12, color="grey"),
            width=12,
            height=12,
            alignment=ft.Alignment(0, 0),
        )

        # 路径显示优化
        self.text_path = ft.Text("", size=11, color="grey", text_align=ft.TextAlign.RIGHT, italic=True)
        self.path_container = ft.Container(content=self.text_path, width=250, alignment=ft.Alignment(1, 0))

        # 布局调整：紧凑单行但分组
        self.row_ctrl = ft.Row(
            [
                ft.Container(content=self.icon_ctrl, width=30, alignment=ft.Alignment(0, 0)),
                ft.Column([
                    ft.Row([
                        ft.Text(f"{self.image_name}", size=14, weight=ft.FontWeight.BOLD, color="onSurface"),
                        ft.Text(f"{self.platform}", size=11, color="onSurfaceVariant")
                    ], spacing=6),
                    ft.Row([
                        self.pull_icon_container, self.text_pull,
                        ft.Container(width=10),
                        self.save_icon_container, self.text_save,
                    ], spacing=2)
                ], spacing=2, expand=True),
                self.path_container
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        super().__init__(
            content=self.row_ctrl,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            border=ft.Border(bottom=ft.BorderSide(1, "outlineVariant")),  # 仅保留底部分割线
            bgcolor="surface",  # 纯白背景
        )

    def _open_path(self, e):
        """Open the file in the system file manager."""
        if not (self.final_path and os.path.exists(self.final_path)):
            return
        try:
            if _platform_mod.system() == "Darwin":
                subprocess.Popen(["open", "-R", self.final_path])
            elif _platform_mod.system() == "Windows":
                subprocess.Popen(["explorer", "/select,", os.path.normpath(self.final_path)])
            else:  # Linux / 其他
                subprocess.Popen(["xdg-open", os.path.dirname(self.final_path)])
        except Exception:
            pass

    def _hover_path(self, e):
        """Handle hover state for the path display."""
        # flet 0.81：下划线等装饰须通过 style=TextStyle 设置，Text 无 decoration 属性
        if e.data == "true":  # 鼠标悬停
            self.text_path.style = ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE)
            self.text_path.color = "primary"
        else:
            self.text_path.style = ft.TextStyle(decoration=ft.TextDecoration.NONE)
            self.text_path.color = "grey"
        try:
            self.text_path.update()
        except Exception:
            pass

    def update_pull(self, status: str, ok: bool | None = None):
        """Update the pull (download) status display."""
        if status == "拉取中...":
            self.icon_ctrl.icon = ft.Icons.RADIO_BUTTON_CHECKED
            self.icon_ctrl.color = "primary"
            self.pull_icon_container.content = ft.ProgressRing(width=12, height=12, stroke_width=2)

        self.text_pull.value = f"{status}"
        if ok is True:
            self.text_pull.color = "green"
            self.pull_icon_container.content = ft.Icon(ft.Icons.DOWNLOAD_DONE, size=12, color="green")
        elif ok is False:
            self.text_pull.color = "red"
            self.pull_icon_container.content = ft.Icon(ft.Icons.ERROR_OUTLINE, size=12, color="red")
        else:
            self.text_pull.color = "primary"
            if status not in ("拉取中...", "等待拉取"):
                self.pull_icon_container.content = ft.Icon(ft.Icons.DOWNLOAD, size=12, color="primary")

    def update_pull_progress(self, done: int, total: int):
        """Update the pull progress display (e.g., 'X/Y layers')."""
        if total > 0:
            self.text_pull.value = f"{done}/{total} 层"
            self.text_pull.color = "primary"

    def update_save(self, status: str, ok: bool | None = None, path: str = ""):
        """Update the save (export) status display."""
        self.text_save.value = f"{status}"
        if "中" in status:
            self.save_icon_container.content = ft.ProgressRing(width=12, height=12, stroke_width=2)

        if path:
            self.final_path = path
            self.text_path.value = os.path.basename(path)
            self.text_path.tooltip = f"在文件管理器中显示:\n{path}"
            self.path_container.on_click = self._open_path
            self.path_container.on_hover = self._hover_path

        if ok is True:
            self.text_save.color = "green"
            self.save_icon_container.content = ft.Icon(ft.Icons.CHECK_CIRCLE, size=12, color="green")
        elif ok is False:
            self.text_save.color = "red"
            self.save_icon_container.content = ft.Icon(ft.Icons.ERROR_OUTLINE, size=12, color="red")
        else:
            self.text_save.color = "primary"
            if "中" not in status:
                self.save_icon_container.content = ft.Icon(ft.Icons.SAVE, size=12, color="primary")

    def complete(self, success: bool):
        """Mark the task as complete with success or failure status."""
        self.is_success = success
        if success:
            self.icon_ctrl.icon = ft.Icons.CHECK_CIRCLE
            self.icon_ctrl.color = "green"
        else:
            self.icon_ctrl.icon = ft.Icons.ERROR
            self.icon_ctrl.color = "red"
