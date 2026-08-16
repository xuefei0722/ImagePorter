"""
Docker 镜像拉取与导出可视化工具（Flet） - UI 现代化重构版

模块结构:
  main.py                     — UI 组装、事件泵与引擎适配层（本文件）
  imageporter/constants.py    — 全局常量与设计令牌
  imageporter/core/docker.py  — Docker CLI 交互
  imageporter/core/parser.py  — 镜像名解析、校验与规范化
  imageporter/core/engine.py  — 任务规划与并发执行引擎（UI 无关，可测试）
  imageporter/ui/task_row.py  — TaskRow 任务行组件
  imageporter/ui/dialogs.py   — 关于/架构对照对话框
  imageporter/utils/config.py — 用户偏好配置
"""

from __future__ import annotations

import asyncio
import os
import threading
from queue import Empty, Queue

import flet as ft

# --- 从拆分模块导入 ---
from imageporter.constants import (
    EVENT_BATCH_LIMIT,
    MAX_CONCURRENCY,
    MAX_LOG_LINES,
    MIN_CONCURRENCY,
    PLATFORM_LABELS,
    PLATFORM_OPTIONS,
    SIDEBAR_WIDTH,
    UI_PUMP_INTERVAL,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from imageporter.core.engine import RunConfig, RunEngine
from imageporter.ui.dialogs import build_about_dialog, build_arch_help_dialog, open_dialog
from imageporter.ui.task_row import TaskRow
from imageporter.utils.config import load_theme_mode, save_theme_mode

# --- Main UI ---

def main(page: ft.Page) -> None:
    page.title = "鲸舟 (ImagePorter)"
    page.window.width = WINDOW_WIDTH
    page.window.height = WINDOW_HEIGHT
    page.padding = 0  # 移除默认内边距，为了让侧边栏贴边

    async def center_window_once_ready() -> None:
        # macOS 下窗口刚创建时尺寸/装饰栏可能尚未稳定，分两次居中更可靠。
        try:
            await page.window.center()
            await asyncio.sleep(0.15)
            await page.window.center()
        except Exception:
            pass

    page.run_task(center_window_once_ready)

    # 配色方案优化：更清爽的蓝白灰
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            surface="#FFFFFF",
            on_surface="#333333",
            on_surface_variant="#64748B",
            outline="#CBD5E1",           # 从 #E2E8F0 加深，对比度 ~1.8:1 → ~2.5:1
            primary="#0066CC",
            error="#EF4444",
        ),
        visual_density=ft.VisualDensity.COMFORTABLE,
    )
    page.dark_theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            surface="#0F172A",
            on_surface="#E2E8F0",
            on_surface_variant="#94A3B8",
            outline="#475569",           # 从 #334155 加亮，对比度 ~1.8:1 → ~3.0:1
            primary="#60A5FA",
            error="#F87171",
        ),
        visual_density=ft.VisualDensity.COMFORTABLE,
    )
    page.theme_mode = load_theme_mode()

    def sync_theme_button() -> None:
        if page.theme_mode == ft.ThemeMode.DARK:
            theme_btn.icon = ft.Icons.LIGHT_MODE
            theme_btn.tooltip = "切换到浅色主题"
        else:
            theme_btn.icon = ft.Icons.DARK_MODE
            theme_btn.tooltip = "切换到深色主题"

    def toggle_theme(_e=None):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.DARK
        if not save_theme_mode(page.theme_mode):
            emit("LOG", msg="[警告] 主题偏好保存失败（无法写入配置文件）")
        sync_theme_button()
        refresh_arch_chip_styles()
        page.update()

    theme_btn = ft.IconButton(
        icon=ft.Icons.DARK_MODE,
        icon_size=18,
        width=26,
        height=26,
        tooltip="切换到深色主题",
        style=ft.ButtonStyle(
            padding=0,
            color="onSurfaceVariant",
            bgcolor={ft.ControlState.HOVERED: "surfaceVariant"},
        ),
        on_click=toggle_theme,
    )
    sync_theme_button()

    # --- 状态变量 ---
    running = {"value": False}
    stop_event = threading.Event()

    # 平台选项、标签和架构对照表均从 constants 模块导入

    # --- 对话框（构建于 ui/dialogs.py） ---
    arch_help_dialog = build_arch_help_dialog(page)
    about_dialog = build_about_dialog(page)

    def open_arch_help(_e=None):
        open_dialog(page, arch_help_dialog, "架构对照表打开失败")

    def open_about_dialog(_e=None):
        open_dialog(page, about_dialog, "关于弹窗打开失败")

    # --- 左侧侧边栏组件 ---

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
    arch_controls = []

    def apply_arch_chip_style(ctr: ft.Container, is_selected: bool) -> None:
        is_dark = page.theme_mode == ft.ThemeMode.DARK
        if is_selected:
            ctr.bgcolor = "#E6F0FF" if not is_dark else "#1E3A5F"
            ctr.border = ft.Border.all(1, "primary")
            ctr.content.color = "primary"
            ctr.content.weight = ft.FontWeight.BOLD
        else:
            ctr.bgcolor = "surface"
            ctr.border = ft.Border.all(1, "outline")
            ctr.content.color = "onSurfaceVariant"
            ctr.content.weight = ft.FontWeight.NORMAL

    def refresh_arch_chip_styles() -> None:
        for ctr in arch_containers.values():
            apply_arch_chip_style(ctr, bool(ctr.data))

    def toggle_arch(e):
        ctr = e.control
        is_selected = not ctr.data
        ctr.data = is_selected
        apply_arch_chip_style(ctr, is_selected)
        ctr.update()

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
            animate=ft.Animation(200, "easeOut"),
        )
        arch_containers[p] = btn
        arch_controls.append(btn)
    refresh_arch_chip_styles()

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
                    on_click=pick_dir_click,  # 点击整个区域都能触发
                    animate=ft.Animation(200, "easeOut"),
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

    # --- 右侧主内容组件 ---

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
    # 结果视图
    result_rows = ft.ListView(spacing=0, auto_scroll=True, expand=True)  # 移除间距，由 TaskRow 内部 Border 控制
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
    tab_btn_log = ft.TextButton(  # 默认灰色
        "运行日志", icon=ft.Icons.TERMINAL, style=ft.ButtonStyle(color="onSurfaceVariant")
    )

    def _set_tab_visible(show_log: bool) -> bool:
        if show_log == log_panel.visible:
            return False
        log_panel.visible = show_log
        task_panel.visible = not show_log
        tab_btn_log.style = ft.ButtonStyle(color="primary" if show_log else "onSurfaceVariant")
        tab_btn_task.style = ft.ButtonStyle(color="onSurfaceVariant" if show_log else "primary")
        return True

    def _switch_tab(show_log: bool, e=None) -> None:
        """统一的 Tab 切换入口（用户点击与引擎事件共用同一逻辑）。"""
        if not _set_tab_visible(show_log):
            return
        if e is not None:  # 用户点击：局部刷新所涉控件
            for ctrl in (log_panel, task_panel, tab_btn_log, tab_btn_task):
                ctrl.update()
        else:  # 程序内部触发：交给统一刷新
            try:
                page.schedule_update()
            except Exception:
                pass

    def switch_to_log(e=None):
        _switch_tab(True, e)

    def switch_to_task(e=None):
        _switch_tab(False, e)

    tab_btn_log.on_click = switch_to_log
    tab_btn_task.on_click = switch_to_task

    tab_bar = ft.Row([tab_btn_task, tab_btn_log], spacing=8)  # 调换渲染顺序
    content_stack = ft.Stack([log_panel, task_panel], expand=True)  # 谁在下面谁显示在上层

    # --- 逻辑控制函数 ---

    ui_events: Queue[dict] = Queue()
    task_rows: dict[str, TaskRow] = {}

    def emit(event_type: str, **payload) -> None:
        ui_events.put({"type": event_type, **payload})

    def _refresh_task_empty_state() -> None:
        has_tasks = len(result_rows.controls) > 0
        result_rows.visible = has_tasks
        task_empty_state.visible = not has_tasks

    def _append_log_line(msg: str) -> None:
        from datetime import datetime as _dt
        now_str = _dt.now().strftime("%H:%M:%S")
        color = "#CCCCCC"
        if "[错误]" in msg or "[失败]" in msg:
            color = "#FF5252"
        elif "[成功]" in msg:
            color = "#69F0AE"
        elif "[警告]" in msg:
            color = "#FFD740"
        elif "[准备]" in msg:
            color = "#40C4FF"
        elif "> " in msg:
            color = "#FFFFFF"
        log_view.controls.append(
            ft.Text(f"[{now_str}] {msg}", font_family="Consolas,Monospace", size=12, color=color, selectable=True)
        )
        if len(log_view.controls) > MAX_LOG_LINES:
            del log_view.controls[: len(log_view.controls) - MAX_LOG_LINES]

    def _apply_summary(stats: dict) -> None:
        total = stats.get("total", 0)
        steps = stats.get("steps", 0)
        status_subtitle.value = (
            f"成功: {stats.get('success', 0)}  /  失败: {stats.get('fail', 0)}  "
            f"/  中止: {stats.get('canceled', 0)}  /  总计: {total}"
        )
        progress_bar.value = (steps / (total * 2)) if total > 0 else 0

    def apply_running_state(flag: bool) -> None:
        running["value"] = flag
        inner_btn = btn_start.content
        inner_btn.disabled = False
        if flag:
            inner_btn.content = get_button_content("中止任务", ft.Icons.STOP_CIRCLE_OUTLINED, "white")
            inner_btn.style.bgcolor = {"": "error", ft.ControlState.HOVERED: "#B91C1C"}
            btn_start.shadow.color = "#66FECACA"
        else:
            inner_btn.content = get_button_content("开始执行", ft.Icons.ROCKET_LAUNCH_ROUNDED, "white")
            inner_btn.style.bgcolor = {"": "primary", ft.ControlState.HOVERED: "#1D4ED8"}
            btn_start.shadow.color = "#66BFDBFE"
        manual_images_input.read_only = flag

    def set_running(flag: bool) -> None:
        apply_running_state(flag)
        page.update()

    async def ui_pump() -> None:
        while True:
            changed = False
            processed = 0
            while processed < EVENT_BATCH_LIMIT:
                try:
                    event = ui_events.get_nowait()
                except Empty:
                    break
                processed += 1
                event_type = event.get("type")

                if event_type == "RESET":
                    task_rows.clear()
                    result_rows.controls.clear()
                    _refresh_task_empty_state()
                    log_view.controls.clear()
                    status_title.value = "正在准备任务..."
                    _apply_summary({})
                    changed = True
                elif event_type == "STATUS":
                    status_title.value = event.get("title", status_title.value)
                    changed = True
                elif event_type == "SUMMARY":
                    _apply_summary(event.get("stats") or {})
                    changed = True
                elif event_type == "LOG":
                    _append_log_line(event.get("msg", ""))
                    changed = True
                elif event_type == "ADD_TASKS":
                    for task in event.get("tasks", []):
                        tid = task["task_id"]
                        row = TaskRow(task["image"], task["platform"])
                        task_rows[tid] = row
                        result_rows.controls.append(row)
                    _refresh_task_empty_state()
                    changed = True
                elif event_type == "SHOW_TASK":
                    changed = _set_tab_visible(False) or changed
                elif event_type == "RUNNING":
                    apply_running_state(bool(event.get("value")))
                    changed = True
                elif event_type == "TASK_PULL_STATUS":
                    row = task_rows.get(event.get("task_id"))
                    if row:
                        row.update_pull(event.get("status", ""), event.get("ok"))
                        changed = True
                elif event_type == "TASK_PULL_PROGRESS":
                    row = task_rows.get(event.get("task_id"))
                    if row:
                        row.update_pull_progress(int(event.get("done", 0)), int(event.get("total", 0)))
                        changed = True
                elif event_type == "TASK_SAVE_STATUS":
                    row = task_rows.get(event.get("task_id"))
                    if row:
                        row.update_save(event.get("status", ""), event.get("ok"), event.get("path", ""))
                        changed = True
                elif event_type == "TASK_COMPLETE":
                    row = task_rows.get(event.get("task_id"))
                    if row:
                        row.complete(bool(event.get("success", False)))
                        changed = True
                elif event_type == "SNACKBAR":
                    # flet 0.81：SnackBar 需挂载 overlay 并置 open=True（Page 无 snack_bar 属性）
                    is_err = bool(event.get("is_error"))
                    page.overlay.append(
                        ft.SnackBar(
                            content=ft.Text(event.get("msg", ""), color="white"),
                            bgcolor="error" if is_err else "primary",
                            duration=4000,
                            open=True,
                        )
                    )
                    changed = True

            if changed:
                try:
                    page.update()
                except Exception:
                    pass
            await asyncio.sleep(UI_PUMP_INTERVAL)

    def run_worker():
        """薄适配层：收集 UI 输入，交给 UI 无关的 RunEngine 执行。"""
        config = RunConfig(
            images_raw=manual_images_input.value or "",
            platforms=[p for p, c in arch_containers.items() if c.data],
            output_dir=output_input.value or "",
            concurrency=int(concurrency_value_text.value or "3"),
            cleanup=cleanup_switch.value,
        )
        RunEngine(config, emit, stop_event).run()

    def on_click_start(e):
        if running["value"]:
            stop_event.set()
            status_title.value = "正在中止..."
            inner_btn = btn_start.content
            inner_btn.disabled = True
            inner_btn.update()
            page.schedule_update()
        else:
            stop_event.clear()
            set_running(True)
            page.run_thread(run_worker)

    # 定义更高级的按钮样式
    def get_button_content(text, icon_name, color):
        return ft.Row(
            [
                ft.Icon(icon_name, size=20, color="white"),
                ft.Text(text, size=16, weight=ft.FontWeight.BOLD, color="white"),
            ],
            alignment=ft.MainAxisAlignment.CENTER,  # 内容居中
            spacing=8
        )

    # 创建按钮实体
    btn_start = ft.Container(
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
            content=get_button_content("开始执行", ft.Icons.ROCKET_LAUNCH_ROUNDED, "white"),
            width=float("inf"),  # 撑满侧边栏宽度
            height=54,           # 增加高度，更容易点击
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.HOVERED: "#1D4ED8",  # blue_700
                    ft.ControlState.DISABLED: "#9CA3AF",  # grey_400
                    "": "primary",  # 默认色
                },
                shape=ft.RoundedRectangleBorder(radius=12),  # 更大的圆角
                elevation=0,  # 关闭默认阴影，使用 Container 的自定义阴影
                padding=0,    # 内边距清零，由 Row 控制
            ),
            on_click=on_click_start,
        )
    )

    # --- 布局组装 ---

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
                            ft.Text("鲸舟 ImagePorter", weight="bold", size=18),
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
                                on_click=open_about_dialog,
                            ),
                        ],
                    ),
                ],
            ),
            ft.Divider(height=1, color="outline"),

            ft.Column(spacing=8, controls=[
                ft.Text("镜像列表", weight="bold", size=14, color="onSurfaceVariant"),
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
                        ft.Text("目标架构", weight="bold", size=14, color="onSurfaceVariant"),
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
                            on_click=open_arch_help,
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.Row(spacing=8, wrap=True, run_spacing=8, controls=arch_controls),
                    bgcolor="transparent"
                )
            ]),

            ft.Column(spacing=8, controls=[
                ft.Text("导出设置", weight="bold", size=14, color="onSurfaceVariant"),
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

    # 右侧内容布局（状态横幅卡片包裹标题/副标题/进度条，消除顶部留白空旷感）
    main_content = ft.Container(
        expand=True,
        bgcolor="surface",
        padding=30,
        content=ft.Column(
            controls=[
                status_banner,
                tab_bar,
                content_stack
            ]
        )
    )

    page.add(
        ft.Row(
            controls=[sidebar, main_content],
            expand=True,
            spacing=0  # 无缝拼接
        )
    )
    page.run_task(ui_pump)


if __name__ == "__main__":
    ft.run(main)
