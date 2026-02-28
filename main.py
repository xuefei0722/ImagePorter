"""
Docker 镜像拉取与导出可视化工具（Flet）。

功能:
1. 直接输入镜像名称（每行一个）
2. 容器架构复选框（可多选）
3. 多镜像并发 pull/save
4. 固定布局的运行监控与日志
"""

from __future__ import annotations

import os
import json
import pty
import re
import select
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import flet as ft

# 匹配 ANSI 转义序列（颜色、光标移动等）
_ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07')


class TaskRow(ft.Container):
    def __init__(self, image: str, platform: str, page: ft.Page):
        self.image = image
        self.platform = platform
        self.is_success = False
        self._page = page
        
        self.icon_ctrl = ft.Icon(ft.Icons.PENDING, color="#38506F", size=18)
        self.text_image = ft.Text(f"{image} [{platform}]", width=300, selectable=True)
        self.text_pull = ft.Text("pull:...", width=90, color="#6B87A8")
        self.text_save = ft.Text("save:...", width=90, color="#6B87A8")
        self.text_path = ft.Text("-", expand=True, selectable=True, color="#6B87A8")
        
        self.row_ctrl = ft.Row(
            [self.icon_ctrl, self.text_image, self.text_pull, self.text_save, self.text_path],
            alignment=ft.MainAxisAlignment.START,
        )
        # 将属性通过构造函数传入，在 Flet 0.80+ 中更可靠
        super().__init__(
            content=self.row_ctrl,
            padding=6,
            border=ft.Border.all(1, "#31465F"),
            border_radius=6,
            bgcolor="#0E1623",
        )

    def update_pull(self, status: str, ok: bool | None = None):
        if status == "进行中...":
            self.icon_ctrl = ft.ProgressRing(width=16, height=16, stroke_width=2, color="#5DA9FF")
            self.row_ctrl.controls[0] = self.icon_ctrl
            
        self.text_pull.value = f"pull:{status}"
        if ok is True:
            self.text_pull.color = ft.Colors.GREEN_400
        elif ok is False:
            self.text_pull.color = ft.Colors.RED_400
        else:
            self.text_pull.color = "#5DA9FF"
        self._page.update()

    def update_pull_progress(self, done: int, total: int):
        """实时更新 pull 层级进度，如 '3/7层'。"""
        if total > 0:
            self.text_pull.value = f"pull:{done}/{total}层"
            self.text_pull.color = "#5DA9FF"
        self._page.update()

    def update_save(self, status: str, ok: bool | None = None, path: str = "-"):
        self.text_save.value = f"save:{status}"
        self.text_path.value = path
        if ok is True:
            self.text_save.color = ft.Colors.GREEN_400
            self.text_path.color = ft.Colors.WHITE
        elif ok is False:
            self.text_save.color = ft.Colors.RED_400
            self.text_path.color = "#B0B0B0"
        else:
            self.text_save.color = "#5DA9FF"
            self.text_path.color = "#5DA9FF"
        self._page.update()

    def complete(self, success: bool):
        self.is_success = success
        if success:
            self.icon_ctrl = ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400, size=18)
        else:
            self.icon_ctrl = ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED_400, size=18)
        self.row_ctrl.controls[0] = self.icon_ctrl
        self._page.update()


def check_docker_available() -> tuple[bool, str]:
    if not shutil.which("docker"):
        return False, "未找到 docker 命令，请先安装并确保在 PATH 中可用。"
    return True, ""


def parse_multiline_images(raw_text: str) -> list[str]:
    images: list[str] = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if line:
            images.append(line)
    return images


def dedup_keep_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def validate_image_name(image: str) -> tuple[bool, str]:
    """校验 Docker 镜像名格式，返回 (是否合法, 错误信息)。"""
    if not image:
        return False, "镜像名不能为空"
    if " " in image or "\t" in image:
        return False, f"镜像名包含空格: '{image}'"
    
    # 分离 registry/name:tag
    # 如果有 tag，先拆出来
    if ":" in image:
        name_part, tag_part = image.rsplit(":", 1)
        if not tag_part:
            return False, f"tag 不能为空: '{image}'"
        # tag 只允许 字母、数字、.、-、_
        if not re.match(r'^[a-zA-Z0-9._-]+$', tag_part):
            return False, f"tag 格式无效 '{tag_part}': 只允许字母、数字、.、-、_"
    else:
        name_part = image
    
    # 检查镜像名是否含大写字母（Docker 镜像名必须全小写）
    # 注意：registry 域名部分可以有大写但不推荐，name 部分必须小写
    # 简化处理：整体检查是否有大写
    if name_part != name_part.lower():
        return False, f"镜像名不能包含大写字母: '{image}'（Docker 要求小写）"
    
    # 检查非法字符
    if not re.match(r'^[a-z0-9][a-z0-9._\-/]*$', name_part):
        return False, f"镜像名格式无效: '{image}'（只允许小写字母、数字、.、-、/、_）"
    
    return True, ""


def run_cmd(cmd: list[str]) -> tuple[bool, str]:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output.strip()


def run_cmd_stream(
    cmd: list[str],
    line_cb: callable | None = None,
) -> tuple[bool, str]:
    """通过 PTY 伪终端流式执行命令，使 Docker 等工具以 TTY 模式实时输出。"""
    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        cmd, stdout=slave_fd, stderr=slave_fd, close_fds=True,
    )
    os.close(slave_fd)

    all_lines: list[str] = []
    buf = ""

    def _flush_lines():
        nonlocal buf
        while "\n" in buf:
            raw, buf = buf.split("\n", 1)
            # 处理 \r：取最后一段（即该行最终状态，跳过中间进度覆写）
            if "\r" in raw:
                raw = raw.split("\r")[-1]
            clean = _ANSI_RE.sub("", raw).strip()
            if clean:
                all_lines.append(clean)
                if line_cb:
                    line_cb(clean)

    while True:
        try:
            rlist, _, _ = select.select([master_fd], [], [], 0.2)
        except (ValueError, OSError):
            break
        if rlist:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            _flush_lines()
        elif proc.poll() is not None:
            # 进程已结束，读取剩余数据
            try:
                while True:
                    rlist, _, _ = select.select([master_fd], [], [], 0.1)
                    if not rlist:
                        break
                    chunk = os.read(master_fd, 4096)
                    if not chunk:
                        break
                    buf += chunk.decode("utf-8", errors="replace")
            except OSError:
                pass
            _flush_lines()
            break

    # 处理残留不完整行
    if buf.strip():
        remaining = buf.split("\r")[-1] if "\r" in buf else buf
        clean = _ANSI_RE.sub("", remaining).strip()
        if clean:
            all_lines.append(clean)
            if line_cb:
                line_cb(clean)

    try:
        os.close(master_fd)
    except OSError:
        pass
    proc.wait()
    return proc.returncode == 0, "\n".join(all_lines)


def get_host_platform() -> str:
    ok, out = run_cmd(["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"])
    if ok and out:
        return out.strip()
    return "linux/amd64"


def get_image_platforms(image: str, log_cb: callable | None = None) -> tuple[list[str], str]:
    if log_cb:
        log_cb(f"  manifest inspect: 正在查询 {image} 支持的平台...")
    import time as _time
    _t0 = _time.time()
    ok, out = run_cmd(["docker", "manifest", "inspect", image])
    _elapsed = _time.time() - _t0
    
    fatal_err = ""
    out_lower = out.lower()
    if not ok:
        if "no such manifest" in out_lower or "not found" in out_lower:
            fatal_err = "镜像不存在"
        elif "denied" in out_lower or "unauthorized" in out_lower:
            fatal_err = "无拉取权限或镜像不存在"

    if log_cb:
        if ok:
            log_cb(f"  manifest inspect: 完成 ({_elapsed:.1f}s)")
        elif fatal_err:
            log_cb(f"  manifest inspect: 严重错误 ({_elapsed:.1f}s) - {fatal_err}")
        else:
            log_cb(f"  manifest inspect: 失败或不可用 ({_elapsed:.1f}s)，将尝试直接拉取")
            
    if not ok:
        return [], fatal_err
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []

    platforms = set()
    for m in data.get("manifests", []):
        p = m.get("platform", {})
        os_name = p.get("os")
        arch = p.get("architecture")
        variant = p.get("variant")
        if os_name and arch:
            platform = f"{os_name}/{arch}"
            if variant:
                platform = f"{platform}/{variant}"
            platforms.add(platform)
    return sorted(platforms), ""


def choose_platforms(image: str, selected_platforms: list[str], host_platform: str, log_cb: callable | None = None) -> tuple[list[str], str]:
    """确定镜像实际要拉取的平台列表。

    优先通过 manifest inspect 获取镜像支持的平台取交集；
    若 manifest inspect 不可用（离线/无 experimental 权限/私有镜像）或交集为空，
    直接信任用户勾选的平台让 docker pull 自行处理。
    若用户未勾选任何平台，则回退到宿主平台。
    """
    available, fatal_err = get_image_platforms(image, log_cb=log_cb)
    if fatal_err:
        return [], fatal_err

    if not selected_platforms:
        # 用户未勾选任何架构 -> 尝试从 manifest 获取合适的平台
        if available:
            preferred = [p for p in available if ("amd64" in p or "arm64" in p)]
            return preferred if preferred else [available[0]], ""
        return [host_platform], ""

    # 用户明确勾选了架构，尝试取和镜像可用平台的交集
    if not available:
        # manifest inspect 失败（离线/无权限且非硬错误）-> 直接使用用户勾选的平台
        return selected_platforms, ""

    selected_set = set(selected_platforms)
    matched = [p for p in available if p in selected_set]
    # 若交集为空，也使用用户勾选，不静默跳过任务
    return matched if matched else selected_platforms, ""


def build_tar_path(image: str, platform: str, output_dir: str) -> str:
    if ":" in image:
        name, tag = image.split(":", 1)
    else:
        name, tag = image, "latest"
    safe_name = name.replace("/", "_")
    safe_plat = platform.replace("/", "_")
    tar_name = f"{safe_name}_{tag}_{safe_plat}.tar"
    return os.path.join(output_dir, tar_name)


def docker_pull(image: str, platform: str, line_cb: callable | None = None) -> tuple[bool, str]:
    return run_cmd_stream(["docker", "pull", "--platform", platform, image], line_cb=line_cb)


def docker_save(image: str, platform: str, output_dir: str, line_cb: callable | None = None) -> tuple[bool, str, str]:
    tar_path = build_tar_path(image, platform, output_dir)
    ok, out = run_cmd_stream(["docker", "save", "-o", tar_path, image], line_cb=line_cb)
    return ok, tar_path, out


def docker_remove(image: str) -> None:
    run_cmd(["docker", "rmi", image])


def main(page: ft.Page) -> None:
    page.title = "鲸舟 (ImagePorter)"
    page.window.width = 1400
    page.window.height = 800
    page.window.min_width = 1200
    page.window.min_height = 760
    page.padding = 14
    page.scroll = ft.ScrollMode.HIDDEN
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#070D16"

    running = {"value": False}
    stop_event = threading.Event()
    images_cache: list[str] = []
    platform_options = [
        "linux/amd64",
        "linux/arm64",
        "linux/arm/v7",
        "linux/arm/v6",
        "linux/386",
        "linux/ppc64le",
        "linux/s390x",
        "linux/riscv64",
    ]

    dir_picker = ft.FilePicker()
    picker_supported = True
    try:
        page.services.append(dir_picker)
    except Exception:
        try:
            page.overlay.extend([dir_picker])
        except Exception:
            picker_supported = False

    output_input = ft.TextField(
        value=".",
        expand=True,
        text_size=13,
        border_color="#38506F",
        focused_border_color="#5DA9FF",
        cursor_color="#9BCCFF",
        color="#EAF4FF",
    )
    manual_images_input = ft.TextField(
        multiline=True,
        expand=True,
        value="",
        text_size=13,
        hint_text="例如:\nnginx:latest\nredis:7\nghcr.io/canner/wren-ui:0.32.2",
        border_color="#38506F",
        focused_border_color="#5DA9FF",
        cursor_color="#9BCCFF",
        color="#EAF4FF",
    )
    concurrency_dropdown = ft.Dropdown(
        width=100,
        value="3",
        text_size=13,
        options=[ft.dropdown.Option(str(i)) for i in range(1, 9)],
    )
    arch_checks: dict[str, ft.Checkbox] = {}
    for p in platform_options:
        arch_checks[p] = ft.Checkbox(label=p, value=(p == "linux/amd64"))
    # 每行两个 checkbox
    _arch_list = list(arch_checks.values())
    arch_rows = []
    for i in range(0, len(_arch_list), 2):
        arch_rows.append(ft.Row(_arch_list[i:i+2], spacing=4))
    cleanup_check = ft.Checkbox(label="导出后删除本地镜像", value=True)

    progress = ft.ProgressBar(value=0.0, expand=True, color="#53A7FF", bgcolor="#1A2637")
    status_text = ft.Text("等待开始", size=14, color="#CFE6FF")
    log_view = ft.ListView(spacing=4, auto_scroll=True)
    result_rows = ft.ListView(spacing=6, auto_scroll=True)
    summary_text = ft.Text("成功: 0, 失败: 0", size=14, color="#DCEEFF")
    loaded_count_text = ft.Text("镜像条目: 0", size=13, color="#9DB8D8")

    def log(msg: str) -> None:
        log_view.controls.append(ft.Text(msg, selectable=True, color="#D4E8FF", size=12))
        page.update()

    def set_running(flag: bool) -> None:
        running["value"] = flag
        if flag:
            start_btn.text = "执行中..."
            start_btn.icon = ft.Icons.HOURGLASS_TOP
            start_btn.style = ft.ButtonStyle(bgcolor="#0F4C8A", color="#7BB8F8", padding=20)
        else:
            start_btn.text = "开始执行"
            start_btn.icon = ft.Icons.PLAY_ARROW
            start_btn.style = ft.ButtonStyle(bgcolor="#1F7AE0", color="#FFFFFF", padding=20)
        start_btn.disabled = flag
        stop_btn.disabled = not flag
        page.update()

    task_stats = {"total": 0, "done": 0, "success": 0, "fail": 0}

    # Flet lock for UI update sequence control
    stats_lock = threading.Lock()

    def update_summary() -> None:
        with stats_lock:
            summary_text.value = f"成功: {task_stats['success']}, 失败: {task_stats['fail']}"
            # 每个子任务分 pull(50%) + save(50%) 两步，总步数 = total * 2
            total_steps = task_stats['total'] * 2
            progress.value = task_stats['steps'] / total_steps if total_steps > 0 else 0
        page.update()

    def on_pick_dir(e: ft.FilePickerResultEvent) -> None:
        if e.path:
            output_input.value = e.path
            page.update()

    try:
        dir_picker.on_result = on_pick_dir
    except Exception:
        pass  # 新版 Flet 可能不支持 on_result

    def get_selected_platforms() -> list[str]:
        return [p for p, c in arch_checks.items() if c.value]

    def refresh_image_count(_e: ft.ControlEvent | None = None) -> None:
        current_images = parse_multiline_images(manual_images_input.value or "")
        loaded_count_text.value = f"镜像条目: {len(dedup_keep_order(current_images))}"
        page.update()

    def process_image(
        image: str,
        platforms: list[str],
        output_dir: str,
        cleanup_enabled: bool,
        task_rows_map: dict[str, TaskRow],
    ) -> None:
        for platform in platforms:
            row = task_rows_map[platform]
            if stop_event.is_set():
                row.update_pull("已中断", False)
                row.complete(False)
                with stats_lock:
                    task_stats["done"] += 1
                    task_stats["fail"] += 1
                    task_stats["steps"] += 2  # 跳过 pull + save
                update_summary()
                continue
            
            log(f"> 开始拉取: {image} ({platform})")
            row.update_pull("进行中...")

            # 使用 set 去重：PTY 模式下 Docker 会用光标上移反复刷新同一层的状态
            _seen_layers: set[str] = set()      # 已发现的层
            _done_layers: set[str] = set()      # 已完成的层
            # 跳过 Docker 交互式进度条的关键词
            _SKIP = ("Downloading", "Extracting", "Waiting", "Verifying")

            def _on_pull_line(line: str) -> None:
                # 过滤掉反复刷新的下载/解压进度行
                if any(kw in line for kw in _SKIP):
                    return
                # 精确去重：PTY 光标上移导致同一行被重复输出
                if line in _seen_lines_set:
                    return
                _seen_lines_set.add(line)
                # 层级进度追踪
                if "Pulling fs layer" in line:
                    lid = line.split(":")[0].strip()
                    _seen_layers.add(lid)
                    row.update_pull_progress(len(_done_layers), len(_seen_layers))
                elif "Already exists" in line:
                    lid = line.split(":")[0].strip()
                    _seen_layers.add(lid)
                    _done_layers.add(lid)
                    row.update_pull_progress(len(_done_layers), len(_seen_layers))
                elif "Pull complete" in line:
                    lid = line.split(":")[0].strip()
                    _done_layers.add(lid)
                    row.update_pull_progress(len(_done_layers), len(_seen_layers))
                log(f"  {line}")

            _seen_lines_set: set[str] = set()
            pull_ok, pull_out = docker_pull(image, platform, line_cb=_on_pull_line)
            
            if not pull_ok:
                row.update_pull("失败", False)
                row.update_save("跳过", False)
                row.complete(False)
                log(f"[失败] 拉取异常: {image} [{platform}]")
                with stats_lock:
                    task_stats["done"] += 1
                    task_stats["fail"] += 1
                    task_stats["steps"] += 2  # 跳过 pull + save
                update_summary()
                continue

            row.update_pull("成功", True)
            with stats_lock:
                task_stats["steps"] += 1  # pull 完成 +1
            update_summary()
            log(f"> 拉取成功，开始导出: {image} ({platform})")
            row.update_save("导出中...")
            
            # docker save 几乎不产生输出，用后台线程监控 tar 文件大小
            import time as _time
            tar_path_expected = build_tar_path(image, platform, output_dir)
            _save_done = threading.Event()
            
            def _save_progress_monitor():
                while not _save_done.is_set():
                    _save_done.wait(5)
                    if _save_done.is_set():
                        break
                    try:
                        if os.path.exists(tar_path_expected):
                            size_mb = os.path.getsize(tar_path_expected) / (1024 * 1024)
                            log(f"  导出中... 已写入 {size_mb:.1f} MB")
                            row.update_save(f"导出中 {size_mb:.0f}MB")
                    except OSError:
                        pass
            
            monitor_thread = threading.Thread(target=_save_progress_monitor, daemon=True)
            monitor_thread.start()
            save_ok, tar_path, save_out = docker_save(image, platform, output_dir, line_cb=lambda l: log(f"  {l}"))
            _save_done.set()
            monitor_thread.join(timeout=1)
            
            if save_ok:
                row.update_save("成功", True, tar_path)
                row.complete(True)
                log(f"[成功] 导出完成: {tar_path}")
                with stats_lock:
                    task_stats["done"] += 1
                    task_stats["success"] += 1
                    task_stats["steps"] += 1  # save 完成 +1
            else:
                row.update_save("失败", False)
                row.complete(False)
                log(f"[失败] 导出异常: {image} [{platform}]\n  {save_out}")
                with stats_lock:
                    task_stats["done"] += 1
                    task_stats["fail"] += 1
                    task_stats["steps"] += 1  # save 完成 +1
                    
            if cleanup_enabled:
                docker_remove(image)
                
            update_summary()

    def run_worker() -> None:
        try:
            log("[准备] 检查 Docker 环境...")
            status_text.value = "检查 Docker 环境"
            progress.value = None  # 不确定态动画
            page.update()
            docker_ok, docker_msg = check_docker_available()
            if not docker_ok:
                log(f"[错误] {docker_msg}")
                status_text.value = "Docker 不可用"
                page.update()
                return

            manual_images = parse_multiline_images(manual_images_input.value or "")
            merged_images = dedup_keep_order(manual_images)
            
            # 格式校验：提前过滤无效镜像名
            valid_images = []
            for img in merged_images:
                ok, err_msg = validate_image_name(img)
                if ok:
                    valid_images.append(img)
                else:
                    log(f"[校验失败] {err_msg}")
            
            if valid_images and len(valid_images) < len(merged_images):
                log(f"[校验] {len(merged_images) - len(valid_images)} 个镜像格式无效已跳过，{len(valid_images)} 个有效")
            
            images_cache.clear()
            images_cache.extend(valid_images)
            loaded_count_text.value = f"镜像条目: {len(images_cache)}"
            page.update()
            if not images_cache:
                log("[警告] 没有可执行镜像，请检查输入的镜像名称格式")
                status_text.value = "无任务"
                page.update()
                return

            output_dir = output_input.value.strip() or "."
            os.makedirs(output_dir, exist_ok=True)

            log("[准备] 检测宿主平台架构...")
            status_text.value = "检测宿主平台"
            page.update()
            host_platform = get_host_platform()
            log(f"  宿主平台: {host_platform}")

            selected_platforms = get_selected_platforms()
            if not selected_platforms:
                log("[警告] 未勾选容器架构，默认回退到宿主平台。")

            image_plan_rows: list[tuple[str, list[str], dict[str, TaskRow]]] = []
            total_tasks = 0
            all_task_rows = []
            
            for idx, image in enumerate(images_cache, 1):
                log(f"[准备] ({idx}/{len(images_cache)}) 查询镜像平台: {image} ...")
                status_text.value = f"查询镜像信息 ({idx}/{len(images_cache)})"
                page.update()
                image_platforms, fatal_err = choose_platforms(
                    image=image,
                    selected_platforms=selected_platforms,
                    host_platform=host_platform,
                    log_cb=log,
                )
                if fatal_err:
                    log(f"[跳过] {image}：{fatal_err}")
                    continue
                if not image_platforms:
                    log(f"[跳过] {image}：未匹配到勾选架构")
                    continue
                
                log(f"  匹配平台: {', '.join(image_platforms)}")
                rows_map = {}
                for p in image_platforms:
                    row = TaskRow(image, p, page)
                    rows_map[p] = row
                    all_task_rows.append(row)
                    
                image_plan_rows.append((image, image_platforms, rows_map))
                total_tasks += len(image_platforms)

            if total_tasks == 0:
                log("[警告] 没有可执行任务")
                status_text.value = "无任务"
                page.update()
                return

            max_workers = int(concurrency_dropdown.value or "1")
            max_workers = max(1, min(max_workers, len(image_plan_rows)))
            log(f"[准备] 任务规划完成，共 {total_tasks} 个子任务，并发 {max_workers}")
            status_text.value = f"执行中: 镜像 {len(image_plan_rows)} 条, 子任务 {total_tasks} 个, 并发 {max_workers}"
            
            with stats_lock:
                task_stats["total"] = total_tasks
                task_stats["done"] = 0
                task_stats["success"] = 0
                task_stats["fail"] = 0
                task_stats["steps"] = 0
                
            progress.value = 0
            result_rows.controls = all_task_rows
            page.update()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        process_image,
                        image,
                        platforms,
                        output_dir,
                        bool(cleanup_check.value),
                        rows_map
                    ): image
                    for image, platforms, rows_map in image_plan_rows
                }
                for future in as_completed(futures):
                    if stop_event.is_set():
                        for f in futures:
                            f.cancel()
                        break
                    image = futures[future]
                    try:
                        future.result()
                    except Exception as ex:
                        log(f"[错误] 任务异常: {image} -> {ex}")

            if stop_event.is_set():
                status_text.value = "已停止"
                log("[信息] 用户请求停止，任务已中断。")
                page.update()

            if not stop_event.is_set():
                status_text.value = "处理完成"
                log("[完成] 所有任务执行结束。")
                page.update()
        finally:
            set_running(False)
            stop_event.clear()

    def start_run(_e: ft.ControlEvent) -> None:
        if running["value"]:
            return
        refresh_image_count()
        log_view.controls.clear()
        result_rows.controls.clear()
        summary_text.value = "成功: 0, 失败: 0"
        progress.value = 0
        stop_event.clear()
        set_running(True)
        status_text.value = "准备执行"
        page.update()
        threading.Thread(target=run_worker, daemon=True).start()

    def stop_run(_e: ft.ControlEvent) -> None:
        if running["value"]:
            stop_event.set()
            status_text.value = "正在停止..."
            page.update()

    start_btn = ft.FilledButton(
        "开始执行",
        icon=ft.Icons.PLAY_ARROW,
        on_click=start_run,
        expand=True,
        style=ft.ButtonStyle(bgcolor="#1F7AE0", color="#FFFFFF", padding=20),
    )
    stop_btn = ft.OutlinedButton(
        "停止",
        icon=ft.Icons.STOP,
        on_click=stop_run,
        disabled=True,
        expand=True,
        style=ft.ButtonStyle(color="#FF5252", padding=20),
    )

    async def pick_dir_click(_e: ft.ControlEvent) -> None:
        result = await dir_picker.get_directory_path()
        if result:
            output_input.value = result
            page.update()

    pick_dir_btn = ft.OutlinedButton(
        "浏览",
        icon=ft.Icons.FOLDER_OPEN,
        disabled=not picker_supported,
        on_click=pick_dir_click,
        style=ft.ButtonStyle(color="#BFD8F7"),
    )
    manual_images_input.on_change = refresh_image_count

    page.add(
        ft.Column(
            expand=True,
            spacing=16,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=20, vertical=16),
                    border_radius=8,
                    bgcolor="#0C1A2A",
                    border=ft.Border.all(1, "#1A2E44"),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.APPS, color="#0DB7ED", size=32),
                                ft.Text("Docker 镜像拉取与导出", size=24, weight=ft.FontWeight.BOLD, color="#F4F9FF"),
                            ], spacing=12),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=12, vertical=4),
                                border_radius=12,
                                bgcolor="#122438",
                                content=ft.Text("离线包工作台", size=12, color="#8DAECC", weight=ft.FontWeight.W_500),
                            ),
                        ],
                    ),
                ),
                ft.Row(
                    expand=True,
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Container(
                            expand=1,
                            padding=16,
                            border=ft.Border.all(1, "#2E4258"),
                            border_radius=8,
                            bgcolor="#0A121E",
                            content=ft.Column(
                                expand=True,
                                spacing=12,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.Icons.SETTINGS, color="#5DA9FF", size=20),
                                        ft.Text("任务配置", size=18, weight=ft.FontWeight.W_600, color="#EEF7FF"),
                                    ], spacing=8),
                                    ft.Divider(height=1, color="#2E4258"),
                                    
                                    ft.Text("保存目录", size=14, weight=ft.FontWeight.W_500, color="#D3E7FF"),
                                    ft.Row([output_input, pick_dir_btn], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                    
                                    ft.Text("并发下载数", size=14, weight=ft.FontWeight.W_500, color="#D3E7FF"),
                                    ft.Row([concurrency_dropdown, cleanup_check], spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                    
                                    ft.Text("容器架构（可多选）", size=14, weight=ft.FontWeight.W_500, color="#D3E7FF"),
                                    ft.Container(
                                        height=140,
                                        border=ft.Border.all(1, "#2E4258"),
                                        border_radius=6,
                                        padding=8,
                                        bgcolor="#0E1725",
                                        content=ft.Column(
                                            spacing=2,
                                            scroll=ft.ScrollMode.AUTO,
                                            controls=arch_rows,
                                        ),
                                    ),
                                    
                                    ft.Row([
                                        ft.Text("镜像输入", size=14, weight=ft.FontWeight.W_500, color="#D3E7FF"), 
                                        loaded_count_text
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    manual_images_input,
                                    
                                    ft.Row([start_btn, stop_btn], spacing=12, alignment=ft.MainAxisAlignment.CENTER),
                                ],
                            ),
                        ),
                        ft.Container(
                            expand=3,
                            padding=16,
                            border=ft.Border.all(1, "#2E4258"),
                            border_radius=8,
                            bgcolor="#0A121E",
                            content=ft.Column(
                                expand=True,
                                spacing=12,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.Icons.MONITOR_HEART, color="#5DA9FF", size=20),
                                        ft.Text("运行监控", size=18, weight=ft.FontWeight.W_600, color="#EEF7FF"),
                                    ], spacing=8),
                                    ft.Divider(height=1, color="#2E4258"),
                                    
                                    ft.Row([
                                        status_text, 
                                        ft.Container(expand=True),
                                        summary_text
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    progress,
                                    
                                    ft.Row([
                                        ft.Icon(ft.Icons.VIEW_LIST, color="#9DB8D8", size=16),
                                        ft.Text("处理结果", size=14, weight=ft.FontWeight.W_500, color="#D3E7FF"),
                                    ], spacing=6),
                                    ft.Container(
                                        expand=True,
                                        height=200,
                                        border=ft.Border.all(1, "#2E4258"),
                                        border_radius=6,
                                        padding=8,
                                        bgcolor="#0E1725",
                                        content=result_rows,
                                    ),
                                    
                                    ft.Row([
                                        ft.Icon(ft.Icons.TERMINAL, color="#9DB8D8", size=16),
                                        ft.Text("运行日志", size=14, weight=ft.FontWeight.W_500, color="#D3E7FF"),
                                    ], spacing=6),
                                    ft.Container(
                                        expand=True,
                                        height=200,
                                        border=ft.Border.all(1, "#2E4258"),
                                        border_radius=6,
                                        padding=8,
                                        bgcolor="#0E1725",
                                        content=log_view,
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ],
        )
    )

    if not picker_supported:
        log("[提示] 当前 Flet 版本不支持目录选择器，请手动输入保存目录路径。")


if __name__ == "__main__":
    ft.run(main)
