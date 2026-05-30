"""CSV/YAML 数据文件读取与用户行分配（供 utils.parametrize 使用）。"""

from __future__ import annotations

import csv
import random
import threading
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ROW_STRATEGIES = {"cycle", "random"}

_FILE_CACHE: dict[Path, list[dict[str, Any]]] = {}
_ALLOCATORS: dict[tuple[Path, str], "UserDataAllocator"] = {}
_CACHE_LOCK = threading.Lock()


def _resolve_data_path(file_name: str) -> Path:
    candidate = Path(file_name)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == "data":
        return PROJECT_ROOT / candidate
    return DATA_DIR / candidate


def _load_from_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        if not reader.fieldnames:
            raise ValueError(f"CSV 文件缺少表头: {path}")
        return [dict(row) for row in reader]


def _load_from_yaml(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    raise ValueError(f"YAML 顶层必须是 mapping 或 list[mapping]: {path}")


def load_rows(file_name: str) -> list[dict[str, Any]]:
    path = _resolve_data_path(file_name)
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在: {path}")

    with _CACHE_LOCK:
        cached = _FILE_CACHE.get(path)
        if cached is not None:
            return cached

        suffix = path.suffix.lower()
        if suffix == ".csv":
            rows = _load_from_csv(path)
        elif suffix in {".yaml", ".yml"}:
            rows = _load_from_yaml(path)
        else:
            raise ValueError(f"仅支持 CSV/YAML 文件: {path}")

        if not rows:
            raise ValueError(f"数据文件为空，无法驱动压测: {path}")
        _FILE_CACHE[path] = rows
        return rows


class UserDataAllocator:
    def __init__(self, rows: list[dict[str, Any]], strategy: str = "cycle"):
        if strategy not in ROW_STRATEGIES:
            raise ValueError(f"不支持的数据分配策略: {strategy}")
        self.rows = rows
        self.strategy = strategy
        self._next_index = 0
        self._assigned: dict[int, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def assign_for_user(self, user_key: int) -> dict[str, Any]:
        with self._lock:
            existing = self._assigned.get(user_key)
            if existing is not None:
                return existing

            if self.strategy == "random":
                row = random.choice(self.rows)
            else:
                row = self.rows[self._next_index % len(self.rows)]
                self._next_index += 1

            snapshot = dict(row)
            self._assigned[user_key] = snapshot
            return snapshot


def _get_allocator(file_name: str, strategy: str) -> UserDataAllocator:
    path = _resolve_data_path(file_name)
    key = (path, strategy)

    with _CACHE_LOCK:
        allocator = _ALLOCATORS.get(key)
        if allocator is not None:
            return allocator

    rows = load_rows(file_name)
    allocator = UserDataAllocator(rows, strategy=strategy)

    with _CACHE_LOCK:
        existing = _ALLOCATORS.get(key)
        if existing is not None:
            return existing
        _ALLOCATORS[key] = allocator
        return allocator


def assign_user_row(user: Any, file_name: str, strategy: str = "cycle") -> dict[str, Any]:
    allocator = _get_allocator(file_name, strategy=strategy)
    return allocator.assign_for_user(id(user))


def clear_data_caches() -> None:
    """切换参数化文件或策略时清空分配器与文件缓存。"""
    with _CACHE_LOCK:
        _FILE_CACHE.clear()
        _ALLOCATORS.clear()
