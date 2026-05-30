"""
接口负载工具：默认结构 + 场景覆盖合并（类似 TS 的 interface + 默认值）。

每个接口在 ``tasks/*_task.py`` 中声明 ``XxxPayload``（TypedDict）与 ``DEFAULT_PAYLOAD``，
任务里一行 ``build_payload(DEFAULT_PAYLOAD, data)`` 即可。
"""

from __future__ import annotations

from typing import Any, Mapping, TypeVar

T = TypeVar("T", bound=Mapping[str, Any])


def build_payload(
    default: T,
    overrides: Mapping[str, Any] | None = None,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """
    用默认负载与场景传入的 data 合并；未传字段保持 DEFAULT 中的硬编码值。

    :param strict: 为 True 时，拒绝 default 中不存在的键（便于排查拼写错误）
    """
    if not overrides:
        return dict(default)

    if strict:
        unknown = set(overrides) - set(default)
        if unknown:
            raise ValueError(f"负载含未定义字段 {sorted(unknown)}，允许字段: {sorted(default)}")

    return {**default, **overrides}


def payload_field_names(default: Mapping[str, Any]) -> tuple[str, ...]:
    """返回契约字段名，供文档或校验使用。"""
    return tuple(default.keys())
