"""左侧边栏：镜像输入、架构选择、导出设置与启动按钮。

main.py 通过 SidebarControls 数据类持有构建产物中需要参与业务逻辑
的控件引用（输入值、选中架构、并发数、清理开关等）。
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

import flet as ft

from imageporter.constants import (
    MAX_CONCURRENCY,
    MIN_CONCURRENCY,
    PLATFORM_LABELS,
    PLATFORM_OPTIONS,
    SIDEBAR_WIDTH,
)


@dataclass
class SidebarControls:
    """main.py 逻辑层需要的侧边栏控件引用集合。"""

    images_input: ft.TextField
    output_input: ft.TextField
    arch_containers: dict[str, ft.Container]
    concurrency_text: ft.Text
    cleanup_switch: ft.Switch
    container: ft.Container

    def selected_platforms(self) -> list[str]:
        """当前勾选的目标架构列表。"""
        return [p for p, c in self.arch_containers.items() if c.data]


def build_button_content(text: str, icon_name) -> ft.Row:
    """主按钮的内容行（图标 + 文案）。"""
    return ft.Row(
        [
            ft.Icon(icon_name, size=20, color="white"),
            ft.Text(text, size=16, weight=ft.FontWeight.BOLD, color="white"),
        ],
        alignment=ft.MainAxisAlignment.CENTER,  # 内容居中
        spacing=8
    )


def build_start_button(on_click: Callable) -> ft.Container:
    """构建「开始/中止执行」主按钮容器。"""
    return ft.Container(
        # 给按钮容器加一点顶部外边距，与上方内容隔开
        margin=ft.Margin(top=20, left=0, right=0, bottom=0),
        # 设置阴影，增加悬浮感
        shadow=ft.BoxShadow(
            blur_radius=15,
            spread_radius=0,
            color="#66BFDBFE",  # 0.4 opacity of blue_200 (BFDBFE)
            offset=ft.Offset(0, 4),
        ),
        content=ft.Button(
            content=build_button_content("开始执行", ft.Icons.ROCKET_LAUNCH_ROUNDED),
            width=float("inf"),  # 撑满侧边栏宽度
            height=54,           # 增加高度，更容易点击
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.HOVERED: "#1D4ED8",  # blue_700
                    ft.ControlState.DISABLED: "#9CA3AF",  # grey_400
                    "": "primary",  # type: ignore[dict-item]  # "" 为 flet 运行时默认态键
                },
                shape=ft.RoundedRectangleBorder(radius=12),  # 更大的圆角
                elevation=0,  # 关闭默认阴影，使用 Container 的自定义阴影
                padding=0,    # 内边距清零，由 Row 控制
            ),
            on_click=on_click,
        ),
    )


def apply_arch_chip_style(ctr: ft.Container, is_selected: bool, is_dark: bool) -> None:
    """按选中态与当前主题应用架构胶囊样式。"""
    label = ctr.content
    assert isinstance(label, ft.Text)  # 胶囊内容固定为文本，同时收窄类型
    if is_selected:
        ctr.bgcolor = "#E6F0FF" if not is_dark else "#1E3A5F"
        ctr.border = ft.Border.all(1, "primary")
        label.color = "primary"
        label.weight = ft.FontWeight.BOLD
    else:
        ctr.bgcolor = "surface"
        ctr.border = ft.Border.all(1, "outline")
        label.color = "onSurfaceVariant"
        label.weight = ft.FontWeight.NORMAL


def refresh_arch_chip_styles(page: ft.Page, arch_containers: dict[str, ft.Container]) -> None:
    """主题切换后按当前明暗模式重刷全部胶囊样式。"""
    is_dark = page.theme_mode == ft.ThemeMode.DARK
    for ctr in arch_containers.values():
        apply_arch_chip_style(ctr, bool(ctr.data), is_dark)


def build_sidebar(
    page: ft.Page,
    theme_btn: ft.IconButton,
    btn_start: ft.Container,
    on_about_click: Callable,
    on_arch_help_click: Callable,
) -> SidebarControls:
    """构建完整侧边栏（含目录选择器注册与架构胶囊交互）。"""

    # 输入框样式优化
    output_input = ft.TextField(
        value=os.path.join(os.path.expanduser("~"), "Downloads"),
        text_size=12,
        height=40,
        content_padding=10,
        border_color="transparent",
        bgcolor="surface",
        expand=True,
        read_only=True,
        hint_text="选择保存路径..."
    )

    dir_picker = ft.FilePicker()

    # 路径显示文本（用于新版表单式布局）
    path_display_text = ft.Text(
        value=os.path.basename(output_input.value) or "选择目录...",
        size=12,
        color="onSurface",
        weight=ft.FontWeight.W_500,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
        width=130,  # 限制宽度防止撑开
    )

    async def pick_dir_click(_e: ft.ControlEvent) -> None:
        result = await dir_picker.get_directory_path()
        if result:
            output_input.value = result
            path_display_text.value = os.path.basename(result) or result
            path_display_text.tooltip = result
            page.update()

    try:
        page.services.append(dir_picker)
    except Exception:
        try:
            page.overlay.append(dir_picker)
        except Exception:
            pass

    manual_images_input = ft.TextField(
        multiline=True,
        min_lines=8,
        max_lines=12,
        text_size=13,
        hint_text="每行一个镜像，例如:\nnginx:latest\nredis:7\n...",
        border_color="transparent",
        bgcolor="surface",
        content_padding=15,
        cursor_color="primary",
    )

    # 架构选择：自定义胶囊样式
    arch_containers: dict[str, ft.Container] = {}
    arch_controls: list[ft.Control] = []

    def toggle_arch(e):
        ctr = e.control
        is_selected = not ctr.data
        ctr.data = is_selected
        apply_arch_chip_style(ctr, is_selected, page.theme_mode == ft.ThemeMode.DARK)
        try:
            ctr.update()  # 控件已挂载时局部刷新（尽力而为）
        except Exception:
            pass

    for p in PLATFORM_OPTIONS:
        short_name, full_desc = PLATFORM_LABELS.get(p, (p.replace("linux/", ""), p))
        is_active = (p == "linux/amd64")
        btn = ft.Container(
            content=ft.Text(
                short_name, size=11,
                color="primary" if is_active else "onSurfaceVariant",
                weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL
            ),
            tooltip=f"{p}\n{full_desc}",
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=4,
            bgcolor="#E6F0FF" if is_active else "surface",
            border=ft.Border.all(1, "primary" if is_active else "outline"),
            on_click=toggle_arch,
            data=is_active,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        arch_containers[p] = btn
        arch_controls.append(btn)
    refresh_arch_chip_styles(page, arch_containers)

    concurrency_value_text = ft.Text("3", size=13, weight=ft.FontWeight.BOLD, width=20, text_align=ft.TextAlign.CENTER)

    def adjust_concurrency(delta):
        current = int(concurrency_value_text.value)
        new_val = max(MIN_CONCURRENCY, min(MAX_CONCURRENCY, current + delta))
        concurrency_value_text.value = str(new_val)
        concurrency_value_text.update()

    cleanup_switch = ft.Switch(value=True, scale=0.7, active_color="primary")

    export_settings_card = ft.Container(
        bgcolor="surface",
        border_radius=8,
        padding=12,
        border=ft.Border.all(1, "outline"),
        content=ft.Column(
            spacing=12,
            controls=[
                # --- 1. 路径选择 (伪装成输入框样式) ---
                ft.Container(
                    bgcolor="surfaceVariant",
                    border_radius=6,
                    border=ft.Border.all(1, "transparent"),  # 预留边框位
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    on_click=pick_dir_click,  # type: ignore[arg-type]  # flet 运行时支持 async 处理器
                    animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=16, color="primary"),
                                path_display_text,
                            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                            ft.Icon(ft.Icons.EDIT_SQUARE, size=14, color="onSurfaceVariant")
                        ]
                    )
                ),

                # --- 分割线 ---
                ft.Divider(height=1, color="outline"),

                # --- 2. 并行任务数 (一体化步进器) ---
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column([
                            ft.Text("并行任务数", size=13, color="onSurface"),
                            ft.Text(
                                f"同时处理的镜像数量 ({MIN_CONCURRENCY}-{MAX_CONCURRENCY})",
                                size=10,
                                color="onSurfaceVariant",
                            ),
                        ], spacing=0),

                        # 步进器容器
                        ft.Container(
                            border=ft.Border.all(1, "outline"),
                            border_radius=4,
                            content=ft.Row(
                                spacing=0,
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.REMOVE,
                                        icon_size=12,
                                        width=28, height=28,
                                        style=ft.ButtonStyle(padding=0, color="onSurfaceVariant"),
                                        on_click=lambda e: adjust_concurrency(-1)
                                    ),
                                    ft.Container(
                                        width=1, height=16, bgcolor="outline"
                                    ),
                                    ft.Container(
                                        content=concurrency_value_text,
                                        padding=ft.Padding.symmetric(horizontal=4)
                                    ),
                                    ft.Container(
                                        width=1, height=16, bgcolor="outline"
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.ADD,
                                        icon_size=12,
                                        width=28, height=28,
                                        style=ft.ButtonStyle(padding=0, color="onSurfaceVariant"),
                                        on_click=lambda e: adjust_concurrency(1)
                                    ),
                                ]
                            )
                        )
                    ]
                ),

                # --- 3. 自动清理 ---
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Column([
                            ft.Text("自动清理", size=13, color="onSurface"),
                            ft.Text("导出后删除本地镜像", size=10, color="onSurfaceVariant"),
                        ], spacing=0),
                        cleanup_switch
                    ]
                ),
            ]
        )
    )

    # 左侧栏布局：上部可滚动，底部按钮固定可见
    sidebar_top = ft.Column(
        spacing=18,
        scroll=None,
        expand=True,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.ANCHOR, color="primary"),
                            ft.Text("鲸舟 ImagePorter", weight=ft.FontWeight.BOLD, size=18),
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        spacing=4,
                        controls=[
                            theme_btn,
                            ft.IconButton(
                                icon=ft.Icons.INFO_OUTLINE,
                                icon_size=18,
                                width=26,
                                height=26,
                                tooltip="关于本开源软件",
                                style=ft.ButtonStyle(
                                    padding=0,
                                    color="onSurfaceVariant",
                                    bgcolor={ft.ControlState.HOVERED: "surfaceVariant"},
                                ),
                                on_click=on_about_click,
                            ),
                        ],
                    ),
                ],
            ),
            ft.Divider(height=1, color="outline"),

            ft.Column(spacing=8, controls=[
                ft.Text("镜像列表", weight=ft.FontWeight.BOLD, size=14, color="onSurfaceVariant"),
                ft.Container(
                    content=manual_images_input,
                    bgcolor="surface", border_radius=8, border=ft.Border.all(1, "outline")
                )
            ]),

            ft.Column(spacing=8, controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                    controls=[
                        ft.Text("目标架构", weight=ft.FontWeight.BOLD, size=14, color="onSurfaceVariant"),
                        ft.IconButton(
                            icon=ft.Icons.HELP_OUTLINE_ROUNDED,
                            icon_size=16,
                            width=24,
                            height=24,
                            tooltip="查看 Docker Hub 架构对照表",
                            style=ft.ButtonStyle(
                                padding=0,
                                color="onSurfaceVariant",
                                bgcolor={ft.ControlState.HOVERED: "surfaceVariant"},
                            ),
                            on_click=on_arch_help_click,
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.Row(spacing=8, wrap=True, run_spacing=8, controls=arch_controls),
                    bgcolor="transparent"
                )
            ]),

            ft.Column(spacing=8, controls=[
                ft.Text("导出设置", weight=ft.FontWeight.BOLD, size=14, color="onSurfaceVariant"),
                export_settings_card,
            ]),
        ],
    )

    sidebar = ft.Container(
        width=SIDEBAR_WIDTH,
        bgcolor="surfaceVariant",
        padding=20,
        content=ft.Column(
            spacing=12,
            expand=True,
            controls=[
                sidebar_top,
                btn_start,
            ],
        ),
    )

    return SidebarControls(
        images_input=manual_images_input,
        output_input=output_input,
        arch_containers=arch_containers,
        concurrency_text=concurrency_value_text,
        cleanup_switch=cleanup_switch,
        container=sidebar,
    )
