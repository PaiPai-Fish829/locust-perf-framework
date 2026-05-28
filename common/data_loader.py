from __future__ import annotations

import csv
import random
import threading
from functools import wraps
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
    """
    将传入路径解析为真实文件路径。

    约定：
    - 传入绝对路径：直接使用；
    - 传入相对路径（如 users.csv）：默认从 data/ 目录读取；
    - 传入 data/xxx.csv：也支持，会被解析到项目根目录。
    """
    candidate = Path(file_name)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == "data":
        return PROJECT_ROOT / candidate
    return DATA_DIR / candidate


def _load_from_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        # 最佳实践：CSV 首行必须是列名，否则 DictReader 会退化成 None key。
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
    """
    通用数据读取器（CSV / YAML）。

    并发安全与性能说明：
    - 文件只在首次读取时进行 I/O，后续从进程内缓存复用，避免每个用户重复读盘；
    - 通过线程锁保护缓存初始化，避免并发场景下同一个文件被重复加载；
    - Locust 用户 greenlet 很多，建议在 on_start 阶段拿到“当前用户的数据快照”并存到实例变量。
    """
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
    """
    将数据行分配给每个虚拟用户。

    - cycle: 按顺序循环分配（第 N 个用户拿第 N 行，超过后回绕）
    - random: 每个用户首次分配时随机抽取一行，并在本用户生命周期内保持稳定
    """

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

            # 返回副本，避免任务函数误改共享原始行。
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
        # 双重检查，避免并发下重复创建。
        existing = _ALLOCATORS.get(key)
        if existing is not None:
            return existing
        _ALLOCATORS[key] = allocator
        return allocator


def assign_user_row(user: Any, file_name: str, strategy: str = "cycle") -> dict[str, Any]:
    """
    语法糖：在 on_start 中为当前虚拟用户分配一条稳定数据。
    """
    allocator = _get_allocator(file_name, strategy=strategy)
    return allocator.assign_for_user(id(user))


def with_user_data(file_name: str, strategy: str = "cycle", attr_name: str = "user_data"):
    """
    装饰器语法糖：把数据行自动挂载到 user.attr_name。

    用法（示例）：
        @with_user_data("users.csv", strategy="cycle")
        def on_start(self):
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            setattr(user, attr_name, assign_user_row(user, file_name=file_name, strategy=strategy))
            return func(user, *args, **kwargs)

        return wrapper

    return decorator


def load_csv_rows(file_path: str) -> list[dict[str, Any]]:
    return load_rows(file_path)


def load_yaml_rows(file_path: str) -> list[dict[str, Any]]:
    return load_rows(file_path)
