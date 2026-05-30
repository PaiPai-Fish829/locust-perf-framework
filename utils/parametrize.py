"""
场景层参数化（仅 scenarios/ 使用）。

- 场景类硬编码 ``default_data_file`` / ``data_strategy``，CLI 无 WebUI 即可运行
- 管理平台 ``scenario_data`` 可在启动时临时覆盖（见 ``set_runtime_overrides``）

用法::

    class LoginScenario(HttpUser):
        default_data_file = "users.yaml"
        data_strategy = "cycle"

        @scenario_cases()
        def on_start(self):
            ...
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Sequence, TypeVar

from config import settings
from utils.data_loader import assign_user_row, clear_data_caches, load_rows

F = TypeVar("F", bound=Callable[..., Any])

DATA_ATTR = "data"
RowDict = dict[str, Any]
DataSource = str | Sequence[RowDict]

# 平台 /platform/swarm 写入：{ "LoginScenario": {"data_file": "...", "data_strategy": "..."} }
_RUNTIME_OVERRIDES: dict[str, dict[str, str]] = {}


def set_runtime_overrides(mapping: dict[str, dict[str, str]] | None) -> None:
    """管理平台启动压测前调用；不传则使用场景类上的默认配置。"""
    global _RUNTIME_OVERRIDES
    _RUNTIME_OVERRIDES = dict(mapping or {})
    clear_data_caches()


def normalize_row(row: RowDict) -> dict[str, Any]:
    """YAML ``data:`` 块、CSV ``data.xxx`` 列或扁平字段 → 请求参数字典。"""
    if not row:
        return {}

    nested = row.get(DATA_ATTR)
    if isinstance(nested, dict):
        return dict(nested)

    data: dict[str, Any] = {}
    prefix = f"{DATA_ATTR}."
    for key, value in row.items():
        key_str = str(key)
        if key_str == DATA_ATTR:
            continue
        if key_str.startswith(prefix):
            data[key_str[len(prefix) :]] = value
        else:
            data[key_str] = value
    return data


def rows_from(source: DataSource) -> list[dict[str, Any]]:
    if isinstance(source, str):
        raw_rows = load_rows(source)
    elif isinstance(source, Sequence) and not isinstance(source, (str, bytes)):
        raw_rows = [dict(row) for row in source]
        if not raw_rows:
            raise ValueError("参数化列表不能为空")
    else:
        raise TypeError(f"不支持的参数化源类型: {type(source)!r}")
    return [normalize_row(row) for row in raw_rows]


def _attach_data_to_user(user: Any, data: dict[str, Any]) -> dict[str, Any]:
    setattr(user, DATA_ATTR, data)
    return data


def bind_scenario_data(
    user: Any,
    source: DataSource,
    *,
    strategy: str = "cycle",
) -> dict[str, Any]:
    """为当前虚拟用户绑定一行请求参数（通常由 ``@scenario_cases`` 调用）。"""
    if isinstance(source, str):
        raw = assign_user_row(user, file_name=source, strategy=strategy)
    else:
        rows = rows_from(source)
        allocator_key = (id(source), strategy)
        cache = getattr(user, "_parametrize_inline_allocator", None)
        if cache is None or cache[0] != allocator_key:
            from utils.data_loader import UserDataAllocator

            cache = (allocator_key, UserDataAllocator(rows, strategy=strategy))
            user._parametrize_inline_allocator = cache
        raw = cache[1].assign_for_user(id(user))

    return _attach_data_to_user(user, normalize_row(raw))


def _resolve_data_config(
    user: Any,
    decorator_file: str | None,
    decorator_strategy: str | None,
) -> tuple[str | None, str]:
    cls = user.__class__
    override = _RUNTIME_OVERRIDES.get(cls.__name__) or {}
    class_file = getattr(cls, "default_data_file", None)
    class_strategy = getattr(cls, "data_strategy", None)

    data_file = (
        override.get("data_file")
        or (decorator_file.strip() if isinstance(decorator_file, str) and decorator_file.strip() else None)
        or (class_file.strip() if isinstance(class_file, str) and class_file.strip() else None)
    )
    if not data_file and _uses_scenario_cases(cls):
        fallback = (settings.DATA_FILE or "").strip()
        data_file = fallback or None

    strategy = (
        override.get("data_strategy")
        or (decorator_strategy.strip() if isinstance(decorator_strategy, str) and decorator_strategy.strip() else None)
        or (class_strategy.strip() if isinstance(class_strategy, str) and class_strategy.strip() else None)
        or settings.DATA_STRATEGY
    )
    return data_file, strategy


def _uses_scenario_cases(user_class: type) -> bool:
    for attr in dir(user_class):
        if getattr(getattr(user_class, attr, None), "_scenario_cases_decorated", False):
            return True
    return bool(getattr(user_class, "parametrized", False))


def scenario_cases(
    source: DataSource | None = None,
    *,
    strategy: str | None = None,
) -> Callable[[F], F]:
    """挂在 ``HttpUser.on_start``：加载参数化并写入 ``self.data``。"""

    decorator_file = source if isinstance(source, str) else None

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            data_file, resolved_strategy = _resolve_data_config(
                user, decorator_file, strategy
            )
            if data_file:
                bind_scenario_data(user, data_file, strategy=resolved_strategy)
            elif source and not isinstance(source, str):
                bind_scenario_data(user, source, strategy=resolved_strategy)
            else:
                _attach_data_to_user(user, {})
            return func(user, *args, **kwargs)

        wrapper._scenario_cases_decorated = True  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


# 兼容旧名
bind_scenario_case = bind_scenario_data
user_cases = scenario_cases
bind_user_case = bind_scenario_data
normalize_case = normalize_row
cases_from = rows_from
