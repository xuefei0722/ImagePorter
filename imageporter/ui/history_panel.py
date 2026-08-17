"""导出历史面板：成功导出记录列表 + 打开定位 / 单条删除 / 一键清空。

仅管理历史记录本身，不触碰已导出的 tar 文件。
"""

from __future__ import annotations

import os
from collections.abc import Callable

import flet as ft

from imageporter.utils.history import ExportRecord, human_file_size


class HistoryPanel:
    """「导出历史」Tab 面板；记录刷新由 main.py 事件泵驱动。"""

    def __init__(
        self,
        on_open: Callable[[str], None],
        on_delete: Callable[[str], None],
        on_clear_all: Callable[[], None],
    ) -> None:
        self._on_open = on_open
        self._on_delete = on_delete
        self._on_clear_all = on_clear_all

        self.count_text = ft.Text("0 条", size=12, color="onSurfaceVariant")
        self.clear_btn = ft.TextButton(
            "清空全部",
            icon=ft.Icons.DELETE_SWEEP_OUTLINED,
            style=ft.ButtonStyle(color="error"),
            visible=False,  # 有记录时才显示
            on_click=lambda e: self._on_clear_all(),
        )
        self.rows_view = ft.ListView(spacing=0, expand=True, visible=False)  # 初始空态
        self.empty_state = ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.HISTORY_TOGGLE_OFF, size=44, color="onSurfaceVariant"),
                    ft.Text("暂无导出历史", size=16, weight=ft.FontWeight.W_500, color="onSurfaceVariant"),
                    ft.Text("成功导出的镜像会自动记录在这里", size=13, color="onSurfaceVariant"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                tight=True,
            ),
            visible=True,
        )
        self.container = ft.Container(
            margin=ft.Margin(top=10, left=0, right=0, bottom=0),
            border_radius=8,
            bgcolor="surface",
            content=ft.Stack([self.rows_view, self.empty_state], expand=True),
            expand=True,
        )
        self.header = ft.Row(
            [
                ft.Text("导出历史", weight=ft.FontWeight.BOLD, size=14, color="onSurfaceVariant"),
                self.count_text,
                ft.Container(expand=True),
                self.clear_btn,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.view = ft.Column([self.header, self.container], spacing=6, expand=True)

    def refresh(self, records: list[ExportRecord]) -> None:
        """按最新记录列表重建行。"""
        self.count_text.value = f"{len(records)} 条"
        self.clear_btn.visible = bool(records)
        self.rows_view.controls = [self._build_row(r) for r in records]
        self.rows_view.visible = bool(records)
        self.empty_state.visible = not records

    def _build_row(self, record: ExportRecord) -> ft.Container:
        exists = os.path.exists(record.tar_path)
        detail_parts = [
            record.timestamp,
            os.path.basename(record.tar_path),
            human_file_size(record.file_size),
        ]
        if not exists:
            detail_parts.append("文件已不在磁盘")
        detail = ft.Text(
            "  ·  ".join(detail_parts),
            size=11,
            color="onSurfaceVariant" if exists else "error",
        )
        open_btn = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            icon_size=16,
            width=30,
            height=30,
            tooltip="在文件管理器中显示",
            style=ft.ButtonStyle(padding=0, color="primary"),
            on_click=lambda e, path=record.tar_path: self._on_open(path),
        )
        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_size=16,
            width=30,
            height=30,
            tooltip="删除此记录（不影响 tar 文件）",
            style=ft.ButtonStyle(padding=0, color="onSurfaceVariant"),
            on_click=lambda e, key=record.key: self._on_delete(key),
        )
        row = ft.Row(
            [
                ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, size=18, color="onSurfaceVariant"),
                ft.Column(
                    [
                        ft.Text(f"{record.image} · {record.platform}", size=13, weight=ft.FontWeight.W_600),
                        detail,
                    ],
                    spacing=2,
                    expand=True,
                ),
                open_btn,
                delete_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.Container(
            content=row,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border=ft.Border(bottom=ft.BorderSide(1, "outlineVariant")),
        )
