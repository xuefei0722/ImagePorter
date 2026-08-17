"""底部环境状态栏：系统信息 + Docker 安装/运行状态一行展示。

状态由 main.py 事件泵经 ENV_STATUS 事件驱动更新，
本组件只做状态变更，不直接触发整页刷新。
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from imageporter.core.docker import DockerEnvStatus
from imageporter.core.environment import (
    DOCKER_DESKTOP_URL,
    DOCKER_DOCS_URL,
    SystemInfo,
    can_launch_docker_desktop,
)


class EnvBar:
    """窗口底部环境状态栏（系统摘要 + Docker 三态指示 + 操作入口）。"""

    def __init__(self, on_refresh: Callable, on_launch: Callable | None = None) -> None:
        self._on_launch = on_launch
        self.system_value = ft.Text("检测中...", size=12, color="onSurfaceVariant")
        self.docker_dot = ft.Icon(ft.Icons.CIRCLE, size=10, color="grey")
        self.docker_state = ft.Text(
            "检测中...", size=12, weight=ft.FontWeight.W_600, color="onSurfaceVariant"
        )
        self.docker_detail = ft.Text("", size=12, color="onSurfaceVariant")
        self.action_btn = ft.TextButton(
            "",
            visible=False,
            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=6), color="primary"),
        )
        self.refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=14,
            width=26,
            height=26,
            tooltip="重新检测 Docker 环境",
            style=ft.ButtonStyle(
                padding=0,
                color="onSurfaceVariant",
                bgcolor={ft.ControlState.HOVERED: "surface"},
            ),
            on_click=on_refresh,
        )
        self.container = ft.Container(
            bgcolor="surfaceVariant",
            padding=ft.Padding.symmetric(horizontal=14, vertical=4),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.COMPUTER_OUTLINED, size=14, color="onSurfaceVariant"),
                    self.system_value,
                    ft.VerticalDivider(width=1, color="outline"),
                    self.docker_dot,
                    self.docker_state,
                    self.docker_detail,
                    self.action_btn,
                    ft.Container(expand=True),
                    self.refresh_btn,
                ],
            ),
        )

    def set_system_info(self, info: SystemInfo) -> None:
        """填充系统摘要（启动时一次性设置）。"""
        self.system_value.value = info.display
        self.system_value.tooltip = f"{info.os_name} {info.os_release} / {info.machine}"

    def _show_action(
        self,
        text: str,
        url: str | None = None,
        on_click: Callable | None = None,
    ) -> None:
        # flet 0.81：TextButton 的标签是 content 属性（无 text 属性）
        self.action_btn.content = text
        self.action_btn.url = url
        self.action_btn.on_click = on_click
        self.action_btn.visible = True

    def set_waiting_launch(self) -> None:
        """点击「启动 Docker Desktop」后的等待态（由下一次 ENV_STATUS 覆盖）。"""
        self.docker_detail.value = "已请求启动，等待守护进程就绪…"
        self.action_btn.visible = False

    def apply_docker_status(self, status: DockerEnvStatus) -> None:
        """按探测结果切换 Docker 状态三态展示与对应操作入口。"""
        if not status.installed:
            self.docker_dot.color = "grey"
            self.docker_state.value = "Docker 未安装"
            self.docker_state.color = "onSurfaceVariant"
            self.docker_detail.value = ""
            self.container.tooltip = "本工具依赖本机 Docker CLI 与守护进程"
            self._show_action("获取 Docker Desktop ↗", url=DOCKER_DESKTOP_URL)
            return
        if not status.running:
            self.docker_dot.color = "red"
            self.docker_state.value = "Docker 未运行"
            self.docker_state.color = "red"
            self.docker_detail.value = "守护进程未响应，任务无法执行"
            self.container.tooltip = (
                f"Docker CLI {status.cli_version}" if status.cli_version else None
            )
            if can_launch_docker_desktop() and self._on_launch is not None:
                self._show_action("启动 Docker Desktop ▶", on_click=self._on_launch)
            else:
                self._show_action("查看 Docker 安装文档 ↗", url=DOCKER_DOCS_URL)
            return
        self.docker_dot.color = "green"
        self.docker_state.value = "Docker 运行中"
        self.docker_state.color = "green"
        self.docker_detail.value = f"{status.server_version} · 引擎 {status.host_platform}"
        self.container.tooltip = (
            "Docker Desktop 的守护进程运行于 Linux 虚拟机（OSType=linux），"
            "容器均为 Linux 环境；架构与「系统」为同一 CPU（命名已统一）"
        )
        self.action_btn.visible = False
