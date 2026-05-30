"""可配置 LoadTestShape 基类：声明默认值与前端可覆盖参数。"""

from __future__ import annotations

import os
from typing import Any, ClassVar

from locust import LoadTestShape


class ConfigurableShape(LoadTestShape):
    """
    压测策略基类。

    子类在文件顶部定义：
    - SHAPE_DEFAULTS：无前端、无环境变量时的默认值（CI / 命令行可直接启动）
    - SHAPE_PARAMS：允许前端覆盖的参数 schema（name / label / min / max / unit）

    优先级：前端 apply_params > 环境变量 LOCUST_SHAPE_<NAME> > SHAPE_DEFAULTS
    """

    abstract: ClassVar[bool] = True

    SHAPE_DEFAULTS: ClassVar[dict[str, int | float]] = {}
    SHAPE_PARAMS: ClassVar[list[dict[str, Any]]] = []

    def __init__(self) -> None:
        super().__init__()
        self._apply_defaults()

    def _env_key(self, name: str) -> str:
        return f"LOCUST_SHAPE_{name.upper()}"

    def _resolve_value(self, name: str, default: int | float) -> int | float:
        raw = os.getenv(self._env_key(name))
        if raw is None or not str(raw).strip():
            return default
        return type(default)(raw)

    def _apply_defaults(self) -> None:
        for name, default in self.SHAPE_DEFAULTS.items():
            setattr(self, name, self._resolve_value(name, default))

    def apply_params(self, overrides: dict[str, int | float] | None = None) -> None:
        """重置为默认值（含环境变量），再应用前端传入的覆盖项。"""
        self._apply_defaults()
        if not overrides:
            return

        allowed = {item["name"] for item in self.SHAPE_PARAMS}
        for name, value in overrides.items():
            if name not in allowed or name not in self.SHAPE_DEFAULTS:
                continue
            default = self.SHAPE_DEFAULTS[name]
            setattr(self, name, type(default)(value))

    @classmethod
    def param_schema(cls) -> list[dict[str, Any]]:
        """供 /platform/shapes 返回的前端表单 schema。"""
        result: list[dict[str, Any]] = []
        for item in cls.SHAPE_PARAMS:
            name = item["name"]
            default = cls.SHAPE_DEFAULTS.get(name)
            result.append(
                {
                    "name": name,
                    "label": item.get("label", name),
                    "unit": item.get("unit", ""),
                    "min": item.get("min"),
                    "max": item.get("max"),
                    "default": default,
                }
            )
        return result
