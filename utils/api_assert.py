"""接口层断言：使用 ``assert``，失败统一抛出 ``ApiAssertionError``。"""

from __future__ import annotations

from typing import Any, Mapping


class ApiAssertionError(AssertionError):
    """接口响应不符合 expvalue 预期。"""


def expected_status_code(expvalue: Mapping[str, Any] | None) -> int:
    if not expvalue:
        return 200
    raw = expvalue.get("status_code", expvalue.get("expected_code", 200))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 200


def assert_http_response(
    response: Any,
    expvalue: Mapping[str, Any] | None,
    request_name: str,
) -> None:
    """
    断言 HTTP 状态码与 ``expvalue`` 一致；通过则标记 Locust ``success()``。

    失败时先 ``response.failure()``（若可用），再抛出 ``ApiAssertionError``。
    """
    expected = expected_status_code(expvalue)
    actual = getattr(response, "status_code", None)
    assert actual is not None, f"[{request_name}] 响应缺少 status_code"

    if actual != expected:
        message = f"[{request_name}] 状态码不符: HTTP {actual}, 预期 {expected}"
        if hasattr(response, "failure"):
            response.failure(message)
        raise ApiAssertionError(message)

    if hasattr(response, "success"):
        response.success()
