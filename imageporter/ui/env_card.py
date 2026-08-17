"""环境状态卡片：系统信息 + Docker 安装/运行状态展示。

状态由 main.py 事件泵经 ENV_STATUS 事件驱动更新，
本组件只做状态变更，不直接触发整页刷新。
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from imageporter.core.docker import DockerEnvStatus
from imageporter.core.environment import SystemInfo


class EnvironmentCard:
    """侧边栏「环境状态」卡片（系统摘要 + Docker 三态指示 + 手动刷新）。"""

    def __init__(self, on_refresh: Callable) -> None:
        self.system_value = ft.Text("检测中...", size=12, color="onSurface")
        self.docker_dot = ft.Icon(ft.Icons.CIRCLE, size=10, color="grey")
        self.docker_state = ft.Text("检测中...", size=12, weight=ft.FontWeight.W_600, color="onSurfaceVariant")
        self.docker_detail = ft.Text("", size=11, color="onSurfaceVariant")
        self.container = ft.Container(
            bgcolor="surface",
            border_radius=8,
            padding=12,
            border=ft.Border.all(1, "outline"),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text("环境状态", size=13, color="onSurface", weight=ft.FontWeight.W_600),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                icon_size=14,
                                width=24,
                                height=24,
                                tooltip="重新检测 Docker 环境",
                                style=ft.ButtonStyle(
                                    padding=0,
                                    color="onSurfaceVariant",
                                    bgcolor={ft.ControlState.HOVERED: "surfaceVariant"},
                                ),
                                on_click=on_refresh,
                            ),
                        ],
                    ),
                    ft.Row(
                        [
                            ft.Container(width=44, content=ft.Text("系统", size=11, color="onSurfaceVariant")),
                            self.system_value,
                        ],
                        spacing=6,
                    ),
                    ft.Row(
                        [self.docker_dot, self.docker_state],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.docker_detail,
                ],
            ),
        )

    def set_system_info(self, info: SystemInfo) -> None:
        """填充系统摘要行（启动时一次性设置）。"""
        self.system_value.value = info.display
        self.system_value.tooltip = f"{info.os_name} {info.os_release} / {info.machine}"

    def apply_docker_status(self, status: DockerEnvStatus) -> None:
        """按探测结果切换 Docker 状态三态展示。"""
        if not status.installed:
            self.docker_dot.color = "grey"
            self.docker_state.value = "Docker 未安装"
            self.docker_state.color = "onSurfaceVariant"
            self.docker_detail.value = "请先安装 Docker Desktop"
            self.container.tooltip = None
            return
        if not status.running:
            self.docker_dot.color = "red"
            self.docker_state.value = "Docker 未运行"
            self.docker_state.color = "red"
            self.docker_detail.value = "请启动 Docker Desktop 后点击 ↻ 重新检测"
            self.container.tooltip = (
                f"Docker CLI {status.cli_version}" if status.cli_version else None
            )
            return
        self.docker_dot.color = "green"
        self.docker_state.value = "Docker 运行中"
        self.docker_state.color = "green"
        self.docker_detail.value = f"服务端 {status.server_version} · 主机 {status.host_platform}"
        self.container.tooltip = (
            f"Docker CLI {status.cli_version}" if status.cli_version else None
        )
