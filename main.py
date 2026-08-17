"""
Docker 镜像拉取与导出可视化工具（Flet） - UI 现代化重构版

模块结构:
  main.py                     — UI 组装、事件泵与引擎适配层（本文件）
  imageporter/constants.py    — 全局常量与设计令牌
  imageporter/core/docker.py  — Docker CLI 交互
  imageporter/core/parser.py  — 镜像名解析、校验与规范化
  imageporter/core/engine.py  — 任务规划与并发执行引擎（UI 无关，可测试）
  imageporter/ui/theme.py     — 明暗主题构建
  imageporter/ui/sidebar.py   — 左侧边栏（镜像输入/架构选择/导出设置/启动按钮）
  imageporter/ui/panels.py    — 右侧主内容面板（状态横幅/日志/任务列表/Tab）
  imageporter/ui/task_row.py  — TaskRow 任务行组件
  imageporter/ui/dialogs.py   — 关于/架构对照对话框
  imageporter/utils/config.py — 用户偏好配置
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from queue import Empty, Queue

import flet as ft

# --- 从拆分模块导入 ---
from imageporter.constants import (
    EVENT_BATCH_LIMIT,
    MAX_LOG_LINES,
    UI_PUMP_INTERVAL,
)
from imageporter.core.docker import (
    DockerEnvStatus,
    list_local_images,
    probe_docker_environment,
    remove_local_images,
)
from imageporter.core.engine import RunConfig, RunEngine
from imageporter.core.environment import (
    EnvRetryWatcher,
    get_system_info,
    launch_docker_desktop,
    run_environment_check,
)
from imageporter.ui.dialogs import (
    build_about_dialog,
    build_arch_help_dialog,
    build_confirm_dialog,
    open_dialog,
)
from imageporter.ui.env_bar import EnvBar
from imageporter.ui.history_panel import HistoryPanel
from imageporter.ui.images_panel import ImagesPanel
from imageporter.ui.panels import (
    TAB_HISTORY,
    TAB_IMAGES,
    TAB_LOG,
    TAB_TASK,
    build_main_panels,
)
from imageporter.ui.sidebar import (
    build_button_content,
    build_sidebar,
    build_start_button,
    refresh_arch_chip_styles,
)
from imageporter.ui.task_row import TaskRow
from imageporter.ui.theme import build_dark_theme, build_light_theme
from imageporter.utils.config import (
    WindowState,
    load_theme_mode,
    load_window_state,
    save_theme_mode,
    save_window_state,
)
from imageporter.utils.history import (
    ExportRecord,
    add_record,
    clear_history,
    load_history,
    remove_record,
)
from imageporter.utils.opener import reveal_in_file_manager

# --- Main UI ---

def main(page: ft.Page) -> None:
    page.title = "鲸舟 (ImagePorter)"
    page.padding = 0  # 移除默认内边距，为了让侧边栏贴边

    # 窗口状态：首次运行默认最大化，之后恢复上次记忆的状态与尺寸。
    # 注意：最大化时不再同时下达 width/height 与 center()——相互矛盾的
    # 尺寸指令会让 macOS 桌面端渲染器停止重绘（表现为整窗黑屏）。
    window_state = load_window_state()
    if window_state.maximized:
        page.window.maximized = True
    else:
        page.window.width = window_state.width
        page.window.height = window_state.height

    _last_window_save = 0.0
    _ui_ready = False  # UI 挂载完成前忽略窗口事件，避免干扰首帧渲染
    _restore_size = {"w": window_state.width, "h": window_state.height}  # 非最大化时尺寸

    def _persist_window(_e=None) -> None:
        """窗口事件节流落盘（事件密集时半秒内只写一次）。"""
        nonlocal _last_window_save
        if not _ui_ready:
            return
        now = time.monotonic()
        if now - _last_window_save < 0.5:
            return
        _last_window_save = now
        try:
            maximized = bool(page.window.maximized)
            if not maximized:
                if page.window.width:
                    _restore_size["w"] = int(page.window.width)
                if page.window.height:
                    _restore_size["h"] = int(page.window.height)
            # 最大化时保存的是还原尺寸，不被全屏尺寸覆盖
            save_window_state(
                WindowState(
                    maximized=maximized,
                    width=_restore_size["w"],
                    height=_restore_size["h"],
                )
            )
        except Exception:
            pass

    page.window.on_event(_persist_window)

    async def center_window_once_ready() -> None:
        # macOS 下窗口刚创建时尺寸/装饰栏可能尚未稳定，分两次居中更可靠；
        # 最大化窗口跳过居中（见上方注释）。
        if page.window.maximized:
            return
        try:
            await page.window.center()
            await asyncio.sleep(0.15)
            await page.window.center()
        except Exception:
            pass

    page.run_task(center_window_once_ready)

    page.theme = build_light_theme()
    page.dark_theme = build_dark_theme()
    page.theme_mode = load_theme_mode()

    # --- 状态变量 ---
    running = {"value": False}
    stop_event = threading.Event()
    ui_events: Queue[dict] = Queue()
    task_rows: dict[str, TaskRow] = {}

    def emit(event_type: str, **payload) -> None:
        ui_events.put({"type": event_type, **payload})

    # --- 主题切换 ---
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
        refresh_arch_chip_styles(page, sidebar.arch_containers)
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

    # --- 对话框（构建于 ui/dialogs.py） ---
    arch_help_dialog = build_arch_help_dialog(page)
    about_dialog = build_about_dialog(page)

    def open_arch_help(_e=None):
        open_dialog(page, arch_help_dialog, "架构对照表打开失败")

    def open_about_dialog(_e=None):
        open_dialog(page, about_dialog, "关于弹窗打开失败")

    # --- 导出历史 / 本机镜像 动作（处理器先行定义，供面板构造引用） ---
    def refresh_history() -> None:
        history_panel.refresh(load_history())

    def _delete_history_record(key: str) -> None:
        history_panel.refresh(remove_record(key))

    def _request_clear_history() -> None:
        count = len(load_history())
        open_dialog(
            page,
            build_confirm_dialog(
                page,
                "清空导出历史",
                f"将删除全部 {count} 条导出记录。此操作仅清除历史记录，"
                "不影响已导出的 tar 文件。",
                "清空",
                lambda: (clear_history(), refresh_history()),
            ),
            "确认框打开失败",
        )

    def refresh_local_images() -> None:
        images, err = list_local_images()
        emit("LOCAL_IMAGES", images=images, error=err)

    def _request_delete_images(refs: list[str]) -> None:
        preview = "\n".join(refs[:8])
        if len(refs) > 8:
            preview += f"\n… 等共 {len(refs)} 个"
        open_dialog(
            page,
            build_confirm_dialog(
                page,
                "删除本地镜像",
                f"将从本机删除以下 {len(refs)} 个镜像并释放相应磁盘空间，"
                f"此操作不可恢复：\n\n{preview}",
                "删除",
                lambda: page.run_thread(_delete_images, refs),
            ),
            "确认框打开失败",
        )

    def _delete_images(refs: list[str]) -> None:
        removed, failed = remove_local_images(refs)
        if removed:
            emit("LOG", msg=f"[成功] 已删除 {len(removed)} 个本地镜像: {', '.join(removed)}")
        for ref, err in failed:
            emit("LOG", msg=f"[失败] 删除 {ref}: {err}")
        emit(
            "SNACKBAR",
            msg=f"已删除 {len(removed)} 个镜像" + (f"，{len(failed)} 个失败" if failed else ""),
            is_error=bool(failed),
        )
        refresh_local_images()

    # --- 右侧主内容面板（构建于 ui/panels.py） ---
    history_panel = HistoryPanel(
        on_open=reveal_in_file_manager,
        on_delete=_delete_history_record,
        on_clear_all=_request_clear_history,
    )
    images_panel = ImagesPanel(
        on_refresh=lambda: page.run_thread(refresh_local_images),
        on_delete_selected=_request_delete_images,
    )
    panels = build_main_panels(history_panel.view, images_panel.view)
    panels.tab_btn_task.on_click = lambda e: panels.switch_tab(TAB_TASK, e, page)
    panels.tab_btn_log.on_click = lambda e: panels.switch_tab(TAB_LOG, e, page)
    panels.tab_btn_history.on_click = lambda e: panels.switch_tab(TAB_HISTORY, e, page)
    panels.tab_btn_images.on_click = lambda e: panels.switch_tab(TAB_IMAGES, e, page)

    # --- 环境状态卡片（系统信息即时填充，Docker 状态后台探测/自动重试） ---
    env_watcher = EnvRetryWatcher(lambda s: emit("ENV_STATUS", status=s))

    def refresh_env_status() -> None:
        status = probe_docker_environment()
        emit("ENV_STATUS", status=status)
        env_watcher.maybe_start(status)  # 不可用时进入周期重试，恢复后自动变绿

    def launch_docker_flow() -> None:
        env_bar.set_waiting_launch()
        if launch_docker_desktop():
            emit("LOG", msg="[提示] 已请求启动 Docker Desktop，等待守护进程就绪…")
            env_watcher.maybe_start(DockerEnvStatus(installed=True, running=False))
        else:
            emit("LOG", msg="[警告] 无法自动启动 Docker Desktop，请手动启动后点击 ↻ 重新检测")
            emit("ENV_STATUS", status=probe_docker_environment())

    env_bar = EnvBar(
        on_refresh=lambda e=None: page.run_thread(refresh_env_status),
        on_launch=lambda e=None: page.run_thread(launch_docker_flow),
    )
    env_bar.set_system_info(get_system_info())

    # --- 逻辑控制函数 ---

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
        panels.log_view.controls.append(
            ft.Text(f"[{now_str}] {msg}", font_family="Consolas,Monospace", size=12, color=color, selectable=True)
        )
        if len(panels.log_view.controls) > MAX_LOG_LINES:
            del panels.log_view.controls[: len(panels.log_view.controls) - MAX_LOG_LINES]

    def _apply_summary(stats: dict) -> None:
        total = stats.get("total", 0)
        steps = stats.get("steps", 0)
        panels.status_subtitle.value = (
            f"成功: {stats.get('success', 0)}  /  失败: {stats.get('fail', 0)}  "
            f"/  中止: {stats.get('canceled', 0)}  /  总计: {total}"
        )
        panels.progress_bar.value = (steps / (total * 2)) if total > 0 else 0

    def apply_running_state(flag: bool) -> None:
        running["value"] = flag
        inner_btn = btn_start.content
        inner_btn.disabled = False
        if flag:
            inner_btn.content = build_button_content("中止任务", ft.Icons.STOP_CIRCLE_OUTLINED)
            inner_btn.style.bgcolor = {"": "error", ft.ControlState.HOVERED: "#B91C1C"}
            btn_start.shadow.color = "#66FECACA"
        else:
            inner_btn.content = build_button_content("开始执行", ft.Icons.ROCKET_LAUNCH_ROUNDED)
            inner_btn.style.bgcolor = {"": "primary", ft.ControlState.HOVERED: "#1D4ED8"}
            btn_start.shadow.color = "#66BFDBFE"
        sidebar.images_input.read_only = flag

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
                    panels.result_rows.controls.clear()
                    panels.refresh_task_empty_state()
                    panels.log_view.controls.clear()
                    panels.status_title.value = "正在准备任务..."
                    _apply_summary({})
                    changed = True
                elif event_type == "STATUS":
                    panels.status_title.value = event.get("title", panels.status_title.value)
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
                        panels.result_rows.controls.append(row)
                    panels.refresh_task_empty_state()
                    changed = True
                elif event_type == "SHOW_TASK":
                    changed = panels.set_active_tab(TAB_TASK) or changed
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
                elif event_type == "ENV_STATUS":
                    env_bar.apply_docker_status(event["status"])
                    changed = True
                elif event_type == "EXPORT_DONE":
                    record = ExportRecord(
                        timestamp=event.get("timestamp", ""),
                        image=event.get("image", ""),
                        platform=event.get("platform", ""),
                        tar_path=event.get("path", ""),
                        file_size=int(event.get("size", 0)),
                    )
                    history_panel.refresh(add_record(record))
                    changed = True
                elif event_type == "LOCAL_IMAGES":
                    images_panel.refresh(event.get("images") or [], error=event.get("error", ""))
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
            images_raw=sidebar.images_input.value or "",
            platforms=sidebar.selected_platforms(),
            output_dir=sidebar.output_input.value or "",
            concurrency=int(sidebar.concurrency_text.value or "3"),
            cleanup=sidebar.cleanup_switch.value,
            compress=sidebar.compress_switch.value,
        )
        RunEngine(config, emit, stop_event).run()
        # 运行结束后刷新环境状态（覆盖运行期间 Docker 被启停的情况）
        refresh_env_status()

    def on_click_start(e):
        if running["value"]:
            stop_event.set()
            panels.status_title.value = "正在中止..."
            inner_btn = btn_start.content
            inner_btn.disabled = True
            inner_btn.update()
            page.schedule_update()
        else:
            stop_event.clear()
            set_running(True)
            page.run_thread(run_worker)

    # --- 布局组装 ---

    btn_start = build_start_button(on_click_start)
    sidebar = build_sidebar(page, theme_btn, btn_start, open_about_dialog, open_arch_help)

    # 右侧内容布局（状态横幅卡片包裹标题/副标题/进度条，消除顶部留白空旷感）
    main_content = ft.Container(
        expand=True,
        bgcolor="surface",
        padding=30,
        content=ft.Column(
            controls=[
                panels.banner,
                panels.tab_bar,
                panels.content_stack
            ]
        )
    )

    page.add(
        ft.Column(
            [
                ft.Row(
                    controls=[sidebar.container, main_content],
                    expand=True,
                    spacing=0,  # 无缝拼接
                ),
                env_bar.container,  # 底部环境状态栏
            ],
            spacing=0,
            expand=True,
        )
    )
    page.run_task(ui_pump)
    _ui_ready = True  # UI 挂载完成，此后窗口事件可持久化
    # 启动即后台探测 Docker 环境与本地镜像列表（不阻塞首屏渲染）
    page.run_thread(refresh_env_status)
    page.run_thread(refresh_local_images)
    refresh_history()


def main_entry() -> None:
    """命令行入口：支持 --check-env 环境自检（安装/排障用）。"""
    if "--check-env" in sys.argv:
        run_environment_check()
        return
    ft.run(main)


if __name__ == "__main__":
    main_entry()
