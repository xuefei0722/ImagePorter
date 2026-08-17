"""Tests for imageporter.core.engine — orchestration without Flet or Docker.

通过记录型 emit 回调断言事件序列，全链 mock Docker 交互。
该套件用于拦截编排层回归（如悬空引用 NameError、统计错算、清理误删）。
"""

from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from imageporter.core.engine import RunConfig, RunEngine


def make_config(**overrides) -> RunConfig:
    defaults = dict(
        images_raw="nginx",
        platforms=["linux/amd64"],
        output_dir=tempfile.gettempdir(),  # 跨平台保证存在
        concurrency=2,
        cleanup=False,
    )
    defaults.update(overrides)
    return RunConfig(**defaults)


class Recorder:
    """记录型 emit 回调：events = [(type, payload), ...]。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def __call__(self, event_type: str, **payload) -> None:
        self.events.append((event_type, payload))

    def types(self) -> list[str]:
        return [t for t, _ in self.events]

    def payloads(self, event_type: str) -> list[dict]:
        return [p for t, p in self.events if t == event_type]

    def last_payload(self, event_type: str) -> dict:
        for t, p in reversed(self.events):
            if t == event_type:
                return p
        raise AssertionError(f"event {event_type!r} not emitted")

    def log_messages(self) -> list[str]:
        return [p.get("msg", "") for p in self.payloads("LOG")]

    def run(self, config: RunConfig, stop_event: threading.Event | None = None) -> Recorder:
        RunEngine(config, self, stop_event or threading.Event()).run()
        return self


class PatchedDockerTestCase(unittest.TestCase):
    """自动应用全链 Docker mock 的基类。"""

    def setUp(self):
        self.mock_check = MagicMock(return_value=(True, ""))
        self.mock_host = MagicMock(return_value="linux/amd64")
        self.mock_choose = MagicMock(side_effect=lambda image, selected, host: (list(selected), ""))
        self.pull = MagicMock(return_value=(True, "pull done"))
        self.save = MagicMock(return_value=(True, "/tmp/out.tar", "save done", 8192))
        self.remove = MagicMock(return_value=None)
        patchers = [
            patch("imageporter.core.engine.check_docker_available", self.mock_check),
            patch("imageporter.core.engine.get_host_platform", self.mock_host),
            patch("imageporter.core.engine.choose_platforms", self.mock_choose),
            patch("imageporter.core.engine.docker_pull", self.pull),
            patch("imageporter.core.engine.docker_save", self.save),
            patch("imageporter.core.engine.docker_remove", self.remove),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)


class TestRunEngineHappyPath(PatchedDockerTestCase):
    def test_full_success_flow(self):
        rec = Recorder().run(make_config(images_raw="nginx\nredis"))
        types = rec.types()

        self.assertEqual(types[0], "RESET")
        self.assertEqual(types[-1], "RUNNING")
        self.assertFalse(rec.last_payload("RUNNING")["value"])
        # 两个镜像 × 一个平台 = 两个任务
        self.assertEqual(len(rec.payloads("ADD_TASKS")[0]["tasks"]), 2)
        completes = rec.payloads("TASK_COMPLETE")
        self.assertEqual(len(completes), 2)
        self.assertTrue(all(c["success"] for c in completes))
        final = rec.last_payload("SUMMARY")["stats"]
        self.assertEqual((final["total"], final["success"], final["fail"], final["steps"]), (2, 2, 0, 4))
        self.assertIn("全部 2 个任务执行成功", rec.last_payload("SNACKBAR")["msg"])

    def test_export_done_emitted_on_save_success(self):
        """导出成功应发出 EXPORT_DONE（含镜像/平台/路径/体积/时间戳）供历史落档。"""
        with patch("imageporter.core.engine.os.path.getsize", return_value=4096):
            rec = Recorder().run(make_config())
        exports = rec.payloads("EXPORT_DONE")
        self.assertEqual(len(exports), 1)
        payload = exports[0]
        self.assertEqual(payload["image"], "nginx")
        self.assertEqual(payload["platform"], "linux/amd64")
        self.assertEqual(payload["path"], "/tmp/out.tar")
        self.assertEqual(payload["size"], 4096)
        self.assertTrue(payload["timestamp"])  # ISO 时间戳非空

    def test_no_export_done_when_save_fails(self):
        self.save.return_value = (False, "/tmp/x.tar", "err")
        rec = Recorder().run(make_config())
        self.assertEqual(rec.payloads("EXPORT_DONE"), [])

    def test_pull_and_save_called_per_task(self):
        Recorder().run(make_config(images_raw="nginx\nredis"))
        self.assertEqual(self.pull.call_count, 2)
        self.assertEqual(self.save.call_count, 2)

    def test_compress_passthrough_default_on(self):
        """RunConfig.compress 默认开启并透传 docker_save。"""
        Recorder().run(make_config())
        self.assertTrue(self.save.call_args.kwargs["compress"])

    def test_compress_passthrough_disabled(self):
        Recorder().run(make_config(compress=False))
        self.assertFalse(self.save.call_args.kwargs["compress"])

    def test_compressed_success_log_includes_ratio(self):
        """压缩模式成功日志应包含原始体积与节省比例。"""
        with patch("imageporter.core.engine.os.path.getsize", return_value=4096):
            rec = Recorder().run(make_config())  # raw_size=8192, final=4096
        success_logs = [m for m in rec.log_messages() if m.startswith("[成功] 导出")]
        self.assertTrue(success_logs)
        self.assertIn("节省 50%", success_logs[0])

    def test_uncompressed_success_log_has_no_ratio(self):
        with patch("imageporter.core.engine.os.path.getsize", return_value=4096):
            rec = Recorder().run(make_config(compress=False))
        success_logs = [m for m in rec.log_messages() if m.startswith("[成功] 导出")]
        self.assertEqual(success_logs, ["[成功] 导出: /tmp/out.tar"])


class TestRunEngineValidation(PatchedDockerTestCase):
    def test_empty_input(self):
        rec = Recorder().run(make_config(images_raw=""))
        self.assertEqual(rec.last_payload("SNACKBAR")["msg"], "请先输入至少一个镜像名称")
        self.assertEqual(rec.last_payload("RUNNING")["value"], False)
        self.assertEqual(rec.payloads("ADD_TASKS"), [])

    def test_docker_unavailable(self):
        self.mock_check.return_value = (False, "daemon down")
        rec = Recorder().run(make_config())
        self.assertEqual(rec.last_payload("SNACKBAR")["msg"], "daemon down")
        self.assertEqual(self.pull.call_count, 0)

    def test_daemon_not_running_message_passes_through(self):
        """H-2：守护进程未运行的错误消息应被引擎原样透传。"""
        self.mock_check.return_value = (False, "Docker 守护进程未运行（请启动 Docker Desktop 后重试）")
        rec = Recorder().run(make_config())
        self.assertIn("守护进程未运行", rec.last_payload("SNACKBAR")["msg"])

    def test_no_platforms_selected(self):
        rec = Recorder().run(make_config(platforms=[]))
        self.assertEqual(rec.last_payload("SNACKBAR")["msg"], "请至少选择一个目标架构")

    def test_output_dir_missing(self):
        rec = Recorder().run(make_config(output_dir="/nonexistent-dir-xyz"))
        self.assertEqual(rec.last_payload("SNACKBAR")["msg"], "输出目录不存在，请重新选择")

    def test_output_dir_not_writable(self):
        with patch("imageporter.core.engine.os.access", return_value=False):
            rec = Recorder().run(make_config())
        self.assertEqual(rec.last_payload("SNACKBAR")["msg"], "输出目录无写入权限，请重新选择")

    def test_all_image_names_invalid(self):
        rec = Recorder().run(make_config(images_raw="NGINX\n:bad"))
        self.assertIn("所有镜像名均无效", rec.last_payload("SNACKBAR")["msg"])

    def test_invalid_names_logged_and_skipped(self):
        rec = Recorder().run(make_config(images_raw="nginx\nNGINX"))
        self.assertTrue(any("镜像名无效" in m for m in rec.log_messages()))
        self.assertEqual(len(rec.payloads("ADD_TASKS")[0]["tasks"]), 1)


class TestRunEngineDedup(PatchedDockerTestCase):
    def test_equivalent_spellings_deduped(self):
        """H-1：nginx / nginx:latest / docker.io/nginx 只应执行一次。"""
        rec = Recorder().run(make_config(images_raw="nginx\nnginx:latest\ndocker.io/nginx"))
        tasks = rec.payloads("ADD_TASKS")[0]["tasks"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["image"], "nginx")  # 保留首个拼写
        self.assertTrue(any("重复" in m for m in rec.log_messages()))

    def test_different_registries_not_deduped(self):
        rec = Recorder().run(make_config(images_raw="nginx\nghcr.io/owner/nginx"))
        self.assertEqual(len(rec.payloads("ADD_TASKS")[0]["tasks"]), 2)

    def test_library_prefix_deduped(self):
        rec = Recorder().run(make_config(images_raw="nginx\nlibrary/nginx"))
        self.assertEqual(len(rec.payloads("ADD_TASKS")[0]["tasks"]), 1)


class TestRunEngineCleanup(PatchedDockerTestCase):
    def test_no_rmi_when_pull_failed(self):
        """H-3：拉取失败（本地可能是用户既有镜像）时不得执行 rmi。"""
        self.pull.return_value = (False, "pull error")
        rec = Recorder().run(make_config(images_raw="nginx", cleanup=True))
        self.remove.assert_not_called()
        final = rec.last_payload("SUMMARY")["stats"]
        self.assertEqual((final["fail"], final["done"]), (1, 1))

    def test_rmi_after_success_when_cleanup_enabled(self):
        Recorder().run(make_config(images_raw="nginx", cleanup=True))
        self.remove.assert_called_once_with("nginx")

    def test_no_rmi_when_cleanup_disabled(self):
        Recorder().run(make_config(images_raw="nginx", cleanup=False))
        self.remove.assert_not_called()


class TestRunEngineStopSemantics(PatchedDockerTestCase):
    def test_stop_before_start_marks_canceled(self):
        stop = threading.Event()
        stop.set()
        rec = Recorder().run(make_config(), stop_event=stop)
        self.save.assert_not_called()
        final = rec.last_payload("SUMMARY")["stats"]
        self.assertEqual(final["canceled"], 1)
        self.assertIn("任务已中止", rec.last_payload("STATUS")["title"])

    def test_stop_during_save_removes_partial_tar(self):
        def stopped_save(image, platform, output_dir, line_cb=None, stop_event=None, compress=False):
            stop_event.set()
            return False, "/tmp/partial.tar", "stopped", 0

        self.save.side_effect = stopped_save
        with patch("imageporter.core.engine.os.path.exists", return_value=True), \
             patch("imageporter.core.engine.os.remove") as mock_remove:
            rec = Recorder().run(make_config())
            mock_remove.assert_called_once_with("/tmp/partial.tar")
        self.assertFalse(rec.payloads("TASK_COMPLETE")[0]["success"])

    def test_pull_stop_emits_cancel_status(self):
        stop = threading.Event()

        def stopped_pull(image, platform, line_cb=None, stop_event=None):
            stop.set()
            return False, "stopped"

        self.pull.side_effect = stopped_pull
        rec = Recorder().run(make_config(), stop_event=stop)
        pull_status = [p["status"] for p in rec.payloads("TASK_PULL_STATUS")]
        self.assertIn("已中止", pull_status)


class TestRunEngineRegressionGuards(PatchedDockerTestCase):
    def test_unexpected_name_error_surfaced_not_crash(self):
        """C-1 回归防护：编排链路任何 NameError 必须以事件形式暴露且不裸崩。"""
        def broken_host_platform():
            raise NameError("name '_env_cache' is not defined")

        self.mock_host.side_effect = broken_host_platform
        rec = Recorder().run(make_config())
        self.assertIn("执行异常", rec.last_payload("SNACKBAR")["msg"])
        self.assertEqual(rec.last_payload("RUNNING")["value"], False)

    def test_concurrency_clamped_to_bounds(self):
        """并发数超界时应收敛到 [MIN_CONCURRENCY, MAX_CONCURRENCY]。"""
        with patch("imageporter.core.engine.ThreadPoolExecutor", wraps=ThreadPoolExecutor) as pool_cls:
            Recorder().run(make_config(concurrency=99))
            self.assertLessEqual(pool_cls.call_args.kwargs["max_workers"], 8)
            self.assertGreaterEqual(pool_cls.call_args.kwargs["max_workers"], 1)

    def test_multi_platform_tasks_serialized_per_image(self):
        self.mock_choose.side_effect = lambda image, selected, host: (["linux/amd64", "linux/arm64"], "")
        rec = Recorder().run(make_config())
        tasks = rec.payloads("ADD_TASKS")[0]["tasks"]
        self.assertEqual(len(tasks), 2)
        # 同一镜像的两个平台任务顺序执行：pull A → save A → pull B → save B
        statuses = [
            p["status"]
            for t, p in rec.events
            if t in ("TASK_SAVE_STATUS", "TASK_PULL_STATUS") and p.get("status") in ("导出完成", "拉取完成")
        ]
        self.assertEqual(statuses, ["拉取完成", "导出完成", "拉取完成", "导出完成"])

    def test_progress_events_emitted_for_layer_lines(self):
        def pull_with_layers(image, platform, line_cb=None, stop_event=None):
            if line_cb:
                line_cb("abc123: Pulling fs layer")
                line_cb("abc123: Pull complete")
            return True, "ok"

        self.pull.side_effect = pull_with_layers
        rec = Recorder().run(make_config())
        progress = rec.payloads("TASK_PULL_PROGRESS")
        self.assertTrue(progress)
        self.assertEqual(progress[-1], {"task_id": "nginx|linux/amd64|0", "done": 1, "total": 1})


if __name__ == "__main__":
    unittest.main()
