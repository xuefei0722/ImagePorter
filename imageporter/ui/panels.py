"""右侧主内容面板：状态横幅、任务/日志/历史/镜像四面板与 Tab 切换。"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

TAB_TASK = "task"
TAB_LOG = "log"
TAB_HISTORY = "history"
TAB_IMAGES = "images"


@dataclass
class MainPanels:
    """main.py 事件泵需要的右侧面板控件引用集合。"""

    status_title: ft.Text
    status_subtitle: ft.Text
    progress_bar: ft.ProgressBar
    banner: ft.Container
    log_view: ft.ListView
    result_rows: ft.ListView
    task_empty_state: ft.Container
    log_panel: ft.Container
    task_panel: ft.Container
    history_area: ft.Control
    images_area: ft.Control
    tab_btn_task: ft.TextButton
    tab_btn_log: ft.TextButton
    tab_btn_history: ft.TextButton
    tab_btn_images: ft.TextButton
    tab_bar: ft.Row
    content_stack: ft.Stack

    def _areas(self) -> dict[str, ft.Control]:
        return {
            TAB_TASK: self.task_panel,
            TAB_LOG: self.log_panel,
            TAB_HISTORY: self.history_area,
            TAB_IMAGES: self.images_area,
        }

    def _buttons(self) -> dict[str, ft.TextButton]:
        return {
            TAB_TASK: self.tab_btn_task,
            TAB_LOG: self.tab_btn_log,
            TAB_HISTORY: self.tab_btn_history,
            TAB_IMAGES: self.tab_btn_images,
        }

    def set_active_tab(self, tab: str) -> bool:
        """切换到指定 Tab；无变化时返回 False。"""
        areas = self._areas()
        if tab not in areas or areas[tab].visible:
            return False
        for key, area in areas.items():
            area.visible = key == tab
        for key, btn in self._buttons().items():
            btn.style = ft.ButtonStyle(color="primary" if key == tab else "onSurfaceVariant")
        return True

    def switch_tab(self, tab: str, e, page: ft.Page) -> None:
        """统一的 Tab 切换入口（用户点击与引擎事件共用同一逻辑）。"""
        if not self.set_active_tab(tab):
            return
        if e is not None:  # 用户点击：局部刷新所涉控件（尽力而为）
            try:
                self.content_stack.update()
                for btn in self._buttons().values():
                    btn.update()
            except Exception:
                pass
        else:  # 程序内部触发：交给统一刷新
            try:
                page.schedule_update()
            except Exception:
                pass

    def refresh_task_empty_state(self) -> None:
        """有任务行时显示列表，否则显示空状态引导。"""
        has_tasks = len(self.result_rows.controls) > 0
        self.result_rows.visible = has_tasks
        self.task_empty_state.visible = not has_tasks


def build_main_panels(history_area: ft.Control, images_area: ft.Control) -> MainPanels:
    """构建右侧主内容全部面板控件（历史/镜像面板由各自模块构建后传入）。"""
    progress_bar = ft.ProgressBar(value=0, color="primary", bgcolor="transparent", height=4)
    status_title = ft.Text("准备就绪", size=20, weight=ft.FontWeight.BOLD)
    status_subtitle = ft.Text("等待任务开始", size=13, color="onSurfaceVariant")

    # 将标题、副标题和进度条整合到一个卡片状的"状态横幅"容器中，消除顶部的留白空旷感
    status_banner = ft.Container(
        content=ft.Column([
            ft.Row(
                [status_title, status_subtitle],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            ft.Container(height=4),  # 间距
            progress_bar
        ], spacing=0),
        bgcolor="surface",  # 浅白表面色，与侧边栏卡片呼应
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
        border_radius=12,
        margin=ft.Margin(top=0, left=0, right=0, bottom=10)  # 撑开与下方 Tab 的距离
    )

    # 日志视图 - 仿终端风格
    log_view = ft.ListView(spacing=2, auto_scroll=True, expand=True, padding=10)
    # 结果视图（移除间距，由 TaskRow 内部 Border 控制）
    result_rows = ft.ListView(spacing=0, auto_scroll=True, expand=True)
    task_empty_state = ft.Container(
        expand=True,
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            [
                ft.Icon(ft.Icons.INBOX_OUTLINED, size=44, color="onSurfaceVariant"),
                ft.Text("暂无任务", size=16, weight=ft.FontWeight.W_500, color="onSurfaceVariant"),
                ft.Text("在左侧输入镜像名称，点击「开始执行」即可", size=13, color="onSurfaceVariant"),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            tight=True,
        ),
        visible=True,
    )

    # 日志面板（暗色终端风格，跨平台通用标题栏）
    log_panel = ft.Container(
        bgcolor="#1E1E1E",
        border_radius=8,
        padding=10,
        margin=ft.Margin(top=10, left=0, right=0, bottom=0),
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.TERMINAL, size=14, color="#888888"),
                ft.Text("Terminal", size=12, color="#888888", font_family="Consolas,Monospace"),
            ], spacing=6),
            ft.Divider(color="#333333"),
            log_view
        ]),
        expand=True,
        visible=False,  # 默认隐藏日志
    )

    # 任务列表面板
    task_panel = ft.Container(
        margin=ft.Margin(top=10, left=0, right=0, bottom=0),
        border_radius=8,
        bgcolor="surface",
        content=ft.Stack([result_rows, task_empty_state], expand=True),
        expand=True,
        visible=True,  # 默认显示任务列表
    )

    # 面板切换按钮
    tab_btn_task = ft.TextButton(  # 默认蓝色高亮
        "任务列表", icon=ft.Icons.LIST_ALT, style=ft.ButtonStyle(color="primary")
    )
    tab_btn_log = ft.TextButton(
        "运行日志", icon=ft.Icons.TERMINAL, style=ft.ButtonStyle(color="onSurfaceVariant")
    )
    tab_btn_history = ft.TextButton(
        "导出历史", icon=ft.Icons.HISTORY, style=ft.ButtonStyle(color="onSurfaceVariant")
    )
    tab_btn_images = ft.TextButton(
        "本机镜像", icon=ft.Icons.DNS_OUTLINED, style=ft.ButtonStyle(color="onSurfaceVariant")
    )

    tab_bar = ft.Row([tab_btn_task, tab_btn_log, tab_btn_history, tab_btn_images], spacing=8)
    content_stack = ft.Stack(  # 后列者显示在上层
        [log_panel, task_panel, history_area, images_area], expand=True
    )

    return MainPanels(
        status_title=status_title,
        status_subtitle=status_subtitle,
        progress_bar=progress_bar,
        banner=status_banner,
        log_view=log_view,
        result_rows=result_rows,
        task_empty_state=task_empty_state,
        log_panel=log_panel,
        task_panel=task_panel,
        history_area=history_area,
        images_area=images_area,
        tab_btn_task=tab_btn_task,
        tab_btn_log=tab_btn_log,
        tab_btn_history=tab_btn_history,
        tab_btn_images=tab_btn_images,
        tab_bar=tab_bar,
        content_stack=content_stack,
    )
