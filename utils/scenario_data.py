"""场景级参数化数据文件：类默认值、平台运行时覆盖。"""

from __future__ import annotations

from typing import Any

from config import settings

# 平台 /platform/swarm 启动前写入：{ "LoginScenario": {"data_file": "...", "data_strategy": "..."} }
_RUNTIME_OVERRIDES: dict[str, dict[str, str]] = {}


def set_runtime_overrides(mapping: dict[str, dict[str, str]] | None) -> None:
    global _RUNTIME_OVERRIDES
    _RUNTIME_OVERRIDES = dict(mapping or {})
    from utils.data_loader import clear_data_caches

    clear_data_caches()


def get_runtime_override(class_name: str) -> dict[str, str] | None:
    raw = _RUNTIME_OVERRIDES.get(class_name)
    if not raw:
        return None
    result: dict[str, str] = {}
    if raw.get("data_file"):
        result["data_file"] = str(raw["data_file"])
    if raw.get("data_strategy"):
        result["data_strategy"] = str(raw["data_strategy"])
    return result or None


def get_class_defaults(user_class: type) -> dict[str, str]:
    result: dict[str, str] = {}
    data_file = getattr(user_class, "default_data_file", None)
    if isinstance(data_file, str) and data_file.strip():
        result["data_file"] = data_file.strip()
    strategy = getattr(user_class, "data_strategy", None)
    if isinstance(strategy, str) and strategy.strip():
        result["data_strategy"] = strategy.strip()
    return result


def resolve_scenario_data_config(
    user: Any,
    decorator_file: str | None,
    decorator_strategy: str | None,
) -> tuple[str | None, str]:
    """解析当前虚拟用户应使用的数据文件与分配策略。"""
    cls = user.__class__
    cls_name = cls.__name__

    override = get_runtime_override(cls_name) or {}
    class_defaults = get_class_defaults(cls)

    data_file = (
        override.get("data_file")
        or (decorator_file.strip() if isinstance(decorator_file, str) and decorator_file.strip() else None)
        or class_defaults.get("data_file")
    )
    if not data_file and _class_uses_parametrize(cls):
        fallback = settings.DATA_FILE.strip() if settings.DATA_FILE else ""
        data_file = fallback or None

    strategy = (
        override.get("data_strategy")
        or (decorator_strategy.strip() if isinstance(decorator_strategy, str) and decorator_strategy.strip() else None)
        or class_defaults.get("data_strategy")
        or settings.DATA_STRATEGY
    )
    return data_file, strategy


def _class_uses_parametrize(user_class: type) -> bool:
    for attr in dir(user_class):
        func = getattr(user_class, attr, None)
        if getattr(func, "_scenario_cases_decorated", False):
            return True
    return bool(getattr(user_class, "parametrized", False))
