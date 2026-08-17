"""与 UI 无关的任务规划与并发执行引擎。

main.py 通过注入 emit 回调将引擎事件转发至 UI 事件队列；
测试可传入记录型回调断言事件序列，无需 Flet 环境与真实 Docker。

事件契约（与 main.py ui_pump 对应）:
  RESET / STATUS / SUMMARY(stats, force) / LOG(msg) / ADD_TASKS(tasks)
  SHOW_TASK / RUNNING(value) / SNACKBAR(msg, is_error)
  TASK_PULL_STATUS(task_id, status, ok) / TASK_PULL_PROGRESS(task_id, done, total)
  TASK_SAVE_STATUS(task_id, status, ok, path) / TASK_COMPLETE(task_id, success)
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

from imageporter.constants import MAX_CONCURRENCY, MIN_CONCURRENCY
from imageporter.core.docker import (
    check_docker_available,
    choose_platforms,
    docker_pull,
    docker_remove,
    docker_save,
    get_host_platform,
)
from imageporter.core.parser import (
    dedup_keep_order,
    normalize_image_identity,
    parse_multiline_images,
    validate_image_name,
)
from imageporter.utils.history import human_file_size

EmitFn = Callable[..., None]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


@dataclass(frozen=True)
class RunConfig:
    """一次工作流的全部用户输入。"""

    images_raw: str
    platforms: list[str]
    output_dir: str
    concurrency: int = 3
    cleanup: bool = True
    compress: bool = True  # gzip 流式压缩导出为 .tar.gz


@dataclass
class RunStats:
    """单次运行的聚合统计（steps 以 pull/save 各一步计）。"""

    total: int = 0
    done: int = 0
    success: int = 0
    fail: int = 0
    canceled: int = 0
    steps: int = 0


class RunEngine:
    """执行完整工作流：输入校验 → 任务规划 → 并发 pull/save。"""

    def __init__(self, config: RunConfig, emit: EmitFn, stop_event: threading.Event) -> None:
        self.config = config
        self.emit = emit
        self.stop_event = stop_event
        self.stats = RunStats()
        self._lock = threading.Lock()

    # --- 统计与事件辅助 ---

    def _stat(self, **delta: int) -> None:
        with self._lock:
            for key, value in delta.items():
                setattr(self.stats, key, getattr(self.stats, key) + value)

    def _snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(vars(self.stats))

    def _summary(self, force: bool = False) -> None:
        self.emit("SUMMARY", force=force, stats=self._snapshot())

    def _fail(self, log_msg: str, snack: str) -> None:
        self.emit("LOG", msg=log_msg)
        self.emit("SNACKBAR", msg=snack, is_error=True)

    # --- 工作流 ---

    def run(self) -> None:
        try:
            self.emit("RESET")
            raw_imgs = parse_multiline_images(self.config.images_raw)
            if not raw_imgs:
                self._fail("[提示] 请输入镜像名称", "请先输入至少一个镜像名称")
                return

            ok, msg = check_docker_available()
            if not ok:
                self._fail(f"[错误] {msg}", msg)
                return

            host_platform = get_host_platform()
            if not self.config.platforms:
                self._fail("[错误] 未选择任何目标架构", "请至少选择一个目标架构")
                return

            if not self._validate_output_dir():
                return

            valid_imgs = self._collect_valid_images(raw_imgs)
            if not valid_imgs:
                self._fail("[错误] 所有镜像名均无效", "所有镜像名均无效，请检查输入格式")
                return

            groups = self._plan_tasks(valid_imgs, host_platform)
            if not groups:
                self.emit("LOG", msg="[结束] 无有效任务")
                self.emit("SNACKBAR", msg="未找到有效的镜像任务，请检查输入", is_error=True)
                return

            self._execute(groups)

            is_stopped = self.stop_event.is_set()
            self.emit("STATUS", title="任务已中止" if is_stopped else "任务完成")
            self._summary(force=True)
            self.emit("LOG", msg="[结束] 流程结束")
            snap = self._snapshot()
            if is_stopped:
                self.emit("SNACKBAR", msg="任务已中止")
            elif snap["fail"] > 0:
                self.emit(
                    "SNACKBAR",
                    msg=f"任务完成：成功 {snap['success']} 个，失败 {snap['fail']} 个",
                    is_error=True,
                )
            else:
                self.emit("SNACKBAR", msg=f"全部 {snap['success']} 个任务执行成功")
        except Exception as e:  # noqa: BLE001 — 顶层兜底，任何异常都需反馈到 UI
            self.emit("LOG", msg=f"[异常] {e}")
            self.emit("SNACKBAR", msg=f"执行异常: {e}", is_error=True)
        finally:
            self.emit("RUNNING", value=False)

    def _validate_output_dir(self) -> bool:
        output_dir = self.config.output_dir
        if not output_dir or not os.path.isdir(output_dir):
            self._fail(f"[错误] 输出目录不存在: {output_dir}", "输出目录不存在，请重新选择")
            return False
        if not os.access(output_dir, os.W_OK):
            self._fail(f"[错误] 输出目录不可写: {output_dir}", "输出目录无写入权限，请重新选择")
            return False
        return True

    def _collect_valid_images(self, raw_imgs: list[str]) -> list[str]:
        """校验镜像名并按规范化身份去重（nginx ≡ nginx:latest 等等价写法）。"""
        valid: list[str] = []
        seen_ids: set[str] = set()
        for img in dedup_keep_order(raw_imgs):
            ok, reason = validate_image_name(img)
            if not ok:
                self.emit("LOG", msg=f"[跳过] 镜像名无效 '{img}': {reason}")
                continue
            identity = normalize_image_identity(img)
            if identity in seen_ids:
                self.emit("LOG", msg=f"[跳过] 与已添加的镜像重复: {img}")
                continue
            seen_ids.add(identity)
            valid.append(img)
        return valid

    def _plan_tasks(
        self, valid_imgs: list[str], host_platform: str
    ) -> list[tuple[str, list[tuple[str, str]]]]:
        """规划任务，返回 [(image, [(platform, task_id), ...]), ...]。"""
        self.emit("STATUS", title="正在规划任务...")
        groups: list[tuple[str, list[tuple[str, str]]]] = []
        task_defs: list[dict] = []
        for img in valid_imgs:
            self.emit("LOG", msg=f"[准备] 分析镜像: {img}")
            target_plats, err = choose_platforms(img, self.config.platforms, host_platform)
            if err:
                self.emit("LOG", msg=f"[跳过] {img}: {err}")
                continue
            task_items: list[tuple[str, str]] = []
            for idx, platform in enumerate(target_plats):
                task_id = f"{img}|{platform}|{idx}"
                task_items.append((platform, task_id))
                task_defs.append({"task_id": task_id, "image": img, "platform": platform})
            if task_items:
                groups.append((img, task_items))

        if not groups:
            return []
        self.emit("ADD_TASKS", tasks=task_defs)
        self.emit("SHOW_TASK")
        self.emit("STATUS", title="正在执行任务")
        self._stat(total=len(task_defs))
        self._summary(force=True)
        return groups

    def _execute(self, groups: list[tuple[str, list[tuple[str, str]]]]) -> None:
        workers = max(MIN_CONCURRENCY, min(MAX_CONCURRENCY, self.config.concurrency))
        pool = ThreadPoolExecutor(max_workers=workers)
        futures = {
            pool.submit(self._process_image, img, items): img
            for img, items in groups
        }
        try:
            for future in as_completed(futures):
                if self.stop_event.is_set():
                    break
                future.result()
        finally:
            if self.stop_event.is_set():
                pool.shutdown(wait=False, cancel_futures=True)
            else:
                pool.shutdown(wait=True)

    def _layer_tracker(self, task_id: str) -> Callable[[str], None]:
        """为单个任务构建输出行回调：去重、跟踪层级进度并转发事件。

        状态封装在闭包内，避免循环变量晚绑定（B023）。
        """
        seen_lines: set[str] = set()
        seen_layers: set[str] = set()
        done_layers: set[str] = set()

        def _on_line(line: str) -> None:
            if any(k in line for k in ("Downloading", "Extracting", "Waiting")):
                return
            if line in seen_lines:
                return
            seen_lines.add(line)
            if "Pulling fs layer" in line:
                seen_layers.add(line.split(":")[0])
            elif "Pull complete" in line:
                done_layers.add(line.split(":")[0])
            self.emit(
                "TASK_PULL_PROGRESS",
                task_id=task_id,
                done=len(done_layers),
                total=len(seen_layers),
            )
            self.emit("LOG", msg=f"  {line}")

        return _on_line

    def _export_success_log(self, tar_path: str, raw_size: int) -> str:
        """构造导出成功日志；压缩模式下附原始体积与节省比例。"""
        base = f"[成功] 导出: {tar_path}"
        if not self.config.compress or raw_size <= 0:
            return base
        try:
            final_size = os.path.getsize(tar_path)
        except OSError:
            return base
        saved_pct = round((1 - final_size / raw_size) * 100)
        return (
            f"{base}（{human_file_size(final_size)}，"
            f"原始 {human_file_size(raw_size)}，节省 {saved_pct}%）"
        )

    def _process_image(self, image: str, task_items: list[tuple[str, str]]) -> None:
        """处理单个镜像的所有目标平台（同一镜像内串行，避免同 tag 自竞争）。"""
        for platform, task_id in task_items:
            if self.stop_event.is_set():
                self.emit("TASK_PULL_STATUS", task_id=task_id, status="已中断", ok=False)
                self.emit("TASK_COMPLETE", task_id=task_id, success=False)
                self._stat(done=1, canceled=1, steps=2)
                self._summary()
                continue

            self.emit("LOG", msg=f"> 开始: {image} ({platform})")
            self.emit("TASK_PULL_STATUS", task_id=task_id, status="拉取中...")

            line_cb = self._layer_tracker(task_id)
            pull_ok, _ = docker_pull(image, platform, line_cb, stop_event=self.stop_event)
            if not pull_ok:
                stopped = self.stop_event.is_set()
                self.emit(
                    "TASK_PULL_STATUS",
                    task_id=task_id,
                    status="已中止" if stopped else "失败",
                    ok=False,
                )
                self.emit("TASK_COMPLETE", task_id=task_id, success=False)
                self.emit("LOG", msg=f"[中止] 拉取: {image}" if stopped else f"[失败] 拉取: {image}")
                if stopped:
                    self._stat(done=1, canceled=1, steps=2)
                else:
                    self._stat(done=1, fail=1, steps=2)
                self._summary()
                continue

            self.emit("TASK_PULL_STATUS", task_id=task_id, status="拉取完成", ok=True)
            self._stat(steps=1)
            self._summary()

            self.emit("TASK_SAVE_STATUS", task_id=task_id, status="导出中...")
            save_ok, tar_path, _, raw_size = docker_save(
                image,
                platform,
                self.config.output_dir,
                stop_event=self.stop_event,
                compress=self.config.compress,
            )

            if save_ok:
                self.emit("TASK_SAVE_STATUS", task_id=task_id, status="导出完成", ok=True, path=tar_path)
                self.emit("TASK_COMPLETE", task_id=task_id, success=True)
                self.emit("LOG", msg=self._export_success_log(tar_path, raw_size))
                # 导出成功 → 通知 UI 层落档历史记录
                self.emit(
                    "EXPORT_DONE",
                    image=image,
                    platform=platform,
                    path=tar_path,
                    size=_file_size(tar_path),
                    timestamp=_now_iso(),
                )
                self._stat(done=1, success=1, steps=1)
            else:
                stopped = self.stop_event.is_set()
                self.emit(
                    "TASK_SAVE_STATUS",
                    task_id=task_id,
                    status="已中止" if stopped else "失败",
                    ok=False,
                )
                self.emit("TASK_COMPLETE", task_id=task_id, success=False)
                if stopped and tar_path and os.path.exists(tar_path):
                    try:
                        os.remove(tar_path)
                    except OSError:
                        pass
                if stopped:
                    self._stat(done=1, canceled=1, steps=1)
                else:
                    self._stat(done=1, fail=1, steps=1)

            # 仅当本轮拉取成功才清理，避免误删用户既有的同名本地镜像
            if self.config.cleanup and pull_ok:
                docker_remove(image)
            self._summary()
