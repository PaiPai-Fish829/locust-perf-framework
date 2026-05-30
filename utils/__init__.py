"""框架通用工具（参数化、形状策略等，与业务 task 解耦）。"""

from utils.api_payload import build_payload, payload_field_names
from utils.parametrize import (
    DATA_ATTR,
    bind_scenario_data,
    rows_from,
    normalize_row,
    scenario_cases,
    set_runtime_overrides,
)

__all__ = [
    "build_payload",
    "payload_field_names",
    "DATA_ATTR",
    "bind_scenario_data",
    "rows_from",
    "normalize_row",
    "scenario_cases",
    "set_runtime_overrides",
]

# 兼容旧名
bind_scenario_case = bind_scenario_data
normalize_case = normalize_row
cases_from = rows_from
