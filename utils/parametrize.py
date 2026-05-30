"""
场景层参数化组件（仅给 scenarios/ 使用，tasks/ 不依赖本模块）。

标准两层：
- ``data``：请求入参，交给 task 函数
- ``expvalue``：响应预期，在 ``tasks/*_task.py`` 内断言

用法::

    from utils.parametrize import bind_scenario_case, scenario_cases, check_expvalue

    class LoginScenario(HttpUser):
        @scenario_cases(settings.DATA_FILE, strategy=settings.DATA_STRATEGY)
        def on_start(self):
            ...

        @task
        def browse_index(self):
            index_task(self.client, self.session, self.data, self.expvalue)
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Sequence, TypeVar

from utils.data_loader import assign_user_row, load_rows

F = TypeVar("F", bound=Callable[..., Any])

CASE_ATTR = "case"
DATA_ATTR = "data"
EXPVALUE_ATTR = "expvalue"

RowDict = dict[str, Any]
CaseDict = dict[str, dict[str, Any]]
CaseSource = str | Sequence[RowDict]

EXPVALUE_KEYS = frozenset({"contains"})
EXP_PREFIXES = ("expvalue.", "exp.")


def normalize_case(row: RowDict) -> CaseDict:
    if not row:
        return {DATA_ATTR: {}, EXPVALUE_ATTR: {}}

    raw_data = row.get(DATA_ATTR)
    raw_exp = row.get(EXPVALUE_ATTR)
    if isinstance(raw_data, dict) and isinstance(raw_exp, dict):
        return {DATA_ATTR: dict(raw_data), EXPVALUE_ATTR: dict(raw_exp)}

    data: dict[str, Any] = {}
    expvalue: dict[str, Any] = {}
    if isinstance(raw_data, dict):
        data.update(raw_data)
    if isinstance(raw_exp, dict):
        expvalue.update(raw_exp)

    for key, value in row.items():
        if key in (DATA_ATTR, EXPVALUE_ATTR):
            continue
        key_str = str(key)
        if key_str.startswith("data."):
            data[key_str[5:]] = value
            continue
        for prefix in EXP_PREFIXES:
            if key_str.startswith(prefix):
                expvalue[key_str[len(prefix) :]] = value
                break
        else:
            if key_str in EXPVALUE_KEYS:
                expvalue[key_str] = value
            else:
                data[key_str] = value

    return {DATA_ATTR: data, EXPVALUE_ATTR: expvalue}


def cases_from(source: CaseSource) -> list[CaseDict]:
    if isinstance(source, str):
        rows = load_rows(source)
    elif isinstance(source, Sequence) and not isinstance(source, (str, bytes)):
        rows = [dict(row) for row in source]
        if not rows:
            raise ValueError("参数化列表不能为空")
    else:
        raise TypeError(f"不支持的参数化源类型: {type(source)!r}")
    return [normalize_case(row) for row in rows]


def _attach_case_to_user(user: Any, case: CaseDict) -> CaseDict:
    setattr(user, CASE_ATTR, case)
    setattr(user, DATA_ATTR, case[DATA_ATTR])
    setattr(user, EXPVALUE_ATTR, case[EXPVALUE_ATTR])
    return case


def bind_scenario_case(
    user: Any,
    source: CaseSource,
    *,
    strategy: str = "cycle",
) -> CaseDict:
    """为当前虚拟用户绑定一行 ``{data, expvalue}``（在 scenario 的 on_start 中调用）。"""
    if isinstance(source, str):
        raw = assign_user_row(user, file_name=source, strategy=strategy)
    else:
        rows = cases_from(source)
        allocator_key = (id(source), strategy)
        cache = getattr(user, "_parametrize_inline_allocator", None)
        if cache is None or cache[0] != allocator_key:
            from utils.data_loader import UserDataAllocator

            cache = (allocator_key, UserDataAllocator(rows, strategy=strategy))
            user._parametrize_inline_allocator = cache
        raw = cache[1].assign_for_user(id(user))

    return _attach_case_to_user(user, normalize_case(raw))


def check_expvalue(response: Any, expvalue: dict[str, Any]) -> None:
    """已弃用：断言请直接写在 ``tasks/*_task.py``。"""
    raise NotImplementedError("请使用 tasks 内硬编码 assert")


def scenario_cases(
    source: CaseSource | None = None,
    *,
    strategy: str | None = None,
) -> Callable[[F], F]:
    """挂在 ``HttpUser.on_start``：加载参数化并写入 ``self.data`` / ``self.expvalue``。

    ``source`` 省略时按顺序解析：平台运行时覆盖 → 场景类 ``default_data_file`` → ``locust-config`` 全局 ``data_file``。
    """

    decorator_file = source if isinstance(source, str) else None

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            from utils.scenario_data import resolve_scenario_data_config

            data_file, resolved_strategy = resolve_scenario_data_config(
                user, decorator_file, strategy
            )
            if data_file:
                bind_scenario_case(user, data_file, strategy=resolved_strategy)
            elif source and not isinstance(source, str):
                bind_scenario_case(user, source, strategy=resolved_strategy)
            else:
                _attach_case_to_user(user, {DATA_ATTR: {}, EXPVALUE_ATTR: {}})
            return func(user, *args, **kwargs)

        wrapper._scenario_cases_decorated = True  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


# 兼容旧名
user_cases = scenario_cases
bind_user_case = bind_scenario_case
