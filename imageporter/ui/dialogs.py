"""关于与架构对照表对话框。

对话框本体在此构建；打开/关闭需要操作 page（overlay 与全局刷新），
由 main.py 通过 open_dialog 驱动，保持模块不反向依赖应用状态。
"""

from __future__ import annotations

import flet as ft

from imageporter import __version__
from imageporter.constants import ARCH_REFERENCE_ROWS

_REPO_URL = "https://github.com/xuefei0722/ImagePorter"


def build_arch_help_dialog(page: ft.Page) -> ft.AlertDialog:
    """构建 Docker Hub 架构对照表对话框。"""
    def close(_e=None):
        dialog.open = False
        page.update()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Docker Hub 架构对照表", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            width=620,
            height=380,
            content=ft.Column(
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text(
                        "不同镜像 Tag 支持的架构会不同，请以仓库 Tag 页面显示为准。",
                        size=12,
                        color="onSurfaceVariant",
                    ),
                    ft.Divider(height=1, color="outline"),
                    *[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.START,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                ft.Container(
                                    width=170, content=ft.Text(platform, size=12, selectable=True)
                                ),
                                ft.Container(
                                    width=110,
                                    content=ft.Text(display_name, size=12, weight=ft.FontWeight.W_600),
                                ),
                                ft.Container(
                                    expand=True,
                                    content=ft.Text(desc, size=12, color="onSurfaceVariant"),
                                ),
                            ],
                        )
                        for platform, display_name, desc in ARCH_REFERENCE_ROWS
                    ],
                ],
            ),
        ),
        actions=[ft.TextButton("关闭", on_click=close)],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    return dialog


def build_about_dialog(page: ft.Page) -> ft.AlertDialog:
    """构建「关于」对话框（版本号取自 imageporter.__version__ 单一来源）。"""
    def close(_e=None):
        dialog.open = False
        page.update()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.INFO_OUTLINE, color="primary"),
                ft.Text("关于鲸舟 (ImagePorter)", weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=560,
            content=ft.Column(
                tight=True,
                spacing=10,
                controls=[
                    ft.Text("Docker 镜像跨设备传导与分发工作台", weight=ft.FontWeight.BOLD),
                    ft.Text(f"版本: v{__version__}"),
                    ft.Text("开源协议: MIT License"),
                    ft.Divider(color="outline"),
                    ft.Text("本软件专为离线部署场景打造，支持多架构镜像处理与并发导出，完全开源且免费使用。"),
                    ft.Row(
                        controls=[
                            ft.TextButton(
                                "访问 GitHub",
                                icon=ft.Icons.OPEN_IN_BROWSER,
                                url=_REPO_URL,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
            ),
        ),
        actions=[ft.TextButton("关闭", on_click=close)],
        actions_alignment=ft.MainAxisAlignment.END,
        bgcolor="surface",
    )
    return dialog


def open_dialog(page: ft.Page, dialog: ft.AlertDialog, error_hint: str) -> None:
    """将对话框挂载到 overlay 并打开；失败时以 SnackBar 提示。

    flet 0.81：SnackBar 同样需要挂载 overlay 并置 open=True，Page 已无
    snack_bar 属性。
    """
    try:
        if dialog not in page.overlay:
            page.overlay.append(dialog)
        dialog.open = True
        page.update()
    except Exception as ex:
        page.overlay.append(ft.SnackBar(ft.Text(f"{error_hint}: {ex}"), open=True))
        page.update()
