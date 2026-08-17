"""本机镜像面板：查看 / 搜索 / 勾选批量删除（删除动作经 main 层确认后执行）。"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from imageporter.core.docker import LocalImage


class ImagesPanel:
    """「本机镜像」Tab 面板；列表刷新由 main.py 经 LOCAL_IMAGES 事件驱动。"""

    def __init__(
        self,
        on_refresh: Callable[[], None],
        on_delete_selected: Callable[[list[str]], None],
    ) -> None:
        self._on_refresh = on_refresh
        self._on_delete_selected = on_delete_selected
        self._all: list[LocalImage] = []
        self._selected: set[str] = set()

        self.count_text = ft.Text("未加载", size=12, color="onSurfaceVariant")
        self.delete_btn = ft.TextButton(
            "",
            icon=ft.Icons.DELETE_OUTLINE,
            style=ft.ButtonStyle(color="error"),
            visible=False,
            on_click=self._request_delete_selected,
        )
        self.search_input = ft.TextField(
            hint_text="搜索镜像名…",
            height=36,
            text_size=12,
            content_padding=8,
            prefix_icon=ft.Icons.SEARCH,
            border_color="outline",
            on_change=lambda e: self._render(),
        )
        self.refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=16,
            width=30,
            height=30,
            tooltip="刷新镜像列表",
            style=ft.ButtonStyle(padding=0, color="primary"),
            on_click=lambda e: self._on_refresh(),
        )
        self.rows_view = ft.ListView(spacing=0, expand=True, visible=False)  # 初始空态
        self.empty_state = ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.DNS_OUTLINED, size=44, color="onSurfaceVariant"),
                    ft.Text("暂无本地镜像", size=16, weight=ft.FontWeight.W_500, color="onSurfaceVariant"),
                    ft.Text("Docker 运行时自动加载，也可点击 ↻ 手动刷新", size=13, color="onSurfaceVariant"),
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
                ft.Text("本机镜像", weight=ft.FontWeight.BOLD, size=14, color="onSurfaceVariant"),
                self.count_text,
                ft.Container(expand=True),
                self.delete_btn,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.toolbar = ft.Row([self.search_input, self.refresh_btn], spacing=8)
        self.view = ft.Column([self.header, self.toolbar, self.container], spacing=6, expand=True)

    def refresh(self, images: list[LocalImage], error: str = "") -> None:
        """替换镜像列表并清空选择。"""
        self._all = list(images)
        self._selected.clear()
        self._sync_delete_btn()
        self._render(error=error)

    def _render(self, error: str = "") -> None:
        query = (self.search_input.value or "").strip().lower()
        shown = [i for i in self._all if query in i.display_name.lower()] if query else self._all
        if error:
            self.count_text.value = "加载失败"
            self.count_text.color = "error"
        elif query:
            self.count_text.value = f"{len(shown)} / {len(self._all)} 个"
            self.count_text.color = "onSurfaceVariant"
        else:
            self.count_text.value = f"{len(shown)} 个" if shown else "0 个"
            self.count_text.color = "onSurfaceVariant"

        self.rows_view.controls = [self._build_row(i) for i in shown]
        self.rows_view.visible = bool(shown)
        self.empty_state.visible = not shown
        if error or not shown:
            empty_column = self.empty_state.content
            assert isinstance(empty_column, ft.Column)  # 收窄类型
            hint = empty_column.controls[1]
            assert isinstance(hint, ft.Text)
            hint.value = "镜像列表加载失败" if error else "暂无本地镜像"
            tip = empty_column.controls[2]
            assert isinstance(tip, ft.Text)
            tip.value = error or "Docker 运行时自动加载，也可点击 ↻ 手动刷新"

    def _build_row(self, image: LocalImage) -> ft.Container:
        checkbox = ft.Checkbox(
            value=image.ref in self._selected,
            scale=0.8,
            on_change=lambda e, ref=image.ref: self._toggle(ref, e.control.value),
        )
        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_size=16,
            width=30,
            height=30,
            tooltip="删除此镜像（需确认）",
            style=ft.ButtonStyle(padding=0, color="error"),
            on_click=lambda e, ref=image.ref: self._on_delete_selected([ref]),
        )
        row = ft.Row(
            [
                checkbox,
                ft.Column(
                    [
                        ft.Text(image.display_name, size=13, weight=ft.FontWeight.W_600),
                        ft.Text(f"{image.created_since} 创建  ·  {image.size}", size=11, color="onSurfaceVariant"),
                    ],
                    spacing=2,
                    expand=True,
                ),
                delete_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.Container(
            content=row,
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border=ft.Border(bottom=ft.BorderSide(1, "outlineVariant")),
        )

    def _toggle(self, ref: str, value: bool) -> None:
        if value:
            self._selected.add(ref)
        else:
            self._selected.discard(ref)
        self._sync_delete_btn()

    def _sync_delete_btn(self) -> None:
        count = len(self._selected)
        # flet 0.81：TextButton 标签是 content 属性
        self.delete_btn.content = f"删除选中 ({count})"
        self.delete_btn.visible = count > 0
        try:
            self.delete_btn.update()
        except Exception:
            pass

    def _request_delete_selected(self, _e=None) -> None:
        if self._selected:
            self._on_delete_selected(sorted(self._selected))
