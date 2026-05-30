"""框架通用工具（参数化、形状策略等，与业务 task 解耦）。"""

from utils.api_assert import ApiAssertionError, assert_http_response
from utils.api_payload import build_payload, payload_field_names
from utils.parametrize import (
    DATA_ATTR,
    EXPVALUE_ATTR,
    bind_scenario_case,
    cases_from,
    check_expvalue,
    normalize_case,
    scenario_cases,
)

__all__ = [
    "ApiAssertionError",
    "assert_http_response",
    "build_payload",
    "payload_field_names",
    "DATA_ATTR",
    "EXPVALUE_ATTR",
    "bind_scenario_case",
    "cases_from",
    "check_expvalue",
    "normalize_case",
    "scenario_cases",
]
