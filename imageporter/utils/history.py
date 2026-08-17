"""导出历史持久化：~/.imageporter/history.json（新记录在前，上限 HISTORY_LIMIT）。"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from imageporter.constants import CACHE_DIR, HISTORY_FILE, HISTORY_LIMIT


@dataclass(frozen=True)
class ExportRecord:
    """一次成功导出的记录。"""

    timestamp: str  # ISO 格式，含秒
    image: str
    platform: str
    tar_path: str
    file_size: int  # 导出时字节数

    @property
    def key(self) -> str:
        """记录唯一键（时间戳 + 路径），供 UI 删除回调用。"""
        return f"{self.timestamp}|{self.tar_path}"


def human_file_size(size: int) -> str:
    """字节数转人类可读（B/KB/MB/GB）。"""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GB"


def load_history() -> list[ExportRecord]:
    """读取历史记录（文件缺失/损坏时返回空列表）。"""
    try:
        if not os.path.isfile(HISTORY_FILE):
            return []
        with open(HISTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        records = []
        for item in data if isinstance(data, list) else []:
            try:
                records.append(
                    ExportRecord(
                        timestamp=str(item["timestamp"]),
                        image=str(item["image"]),
                        platform=str(item["platform"]),
                        tar_path=str(item["tar_path"]),
                        file_size=int(item.get("file_size", 0)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue  # 跳过损坏条目
        return records
    except Exception:
        return []


def save_history(records: list[ExportRecord]) -> bool:
    """写入历史记录（调用方负责截断到上限）。"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def add_record(record: ExportRecord) -> list[ExportRecord]:
    """头部插入新记录并持久化，返回更新后的列表。"""
    records = [record, *load_history()][:HISTORY_LIMIT]
    save_history(records)
    return records


def remove_record(key: str) -> list[ExportRecord]:
    """按键删除单条记录并持久化，返回更新后的列表。"""
    records = [r for r in load_history() if r.key != key]
    save_history(records)
    return records


def clear_history() -> None:
    """清空全部历史记录。"""
    save_history([])
