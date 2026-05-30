import importlib
import os
from pathlib import Path
from locust import LoadTestShape

from scenarios.add_location_flow import AddLocationFlowScenario
from scenarios.login_scenario import LoginScenario

from common import metrics, platform_api  # noqa: F401  # side-effect: /metrics、/platform/*

__all__ = ["AddLocationFlowScenario", "LoginScenario"]

# 注册 shapes/ 下所有非 abstract 的 LoadTestShape，供管理平台选择并通过 shape_class 启动。
# 必须写入 locustfile 模块 globals，Locust 才会纳入 available_shape_classes。
for shape_file in sorted(Path(__file__).parent.joinpath("shapes").glob("*.py")):
    if shape_file.name.startswith("_"):
        continue
    module = importlib.import_module(f"shapes.{shape_file.stem}")
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if (
            isinstance(obj, type)
            and issubclass(obj, LoadTestShape)
            and obj is not LoadTestShape
            and not getattr(obj, "abstract", False)
            and attr_name not in __all__
        ):
            globals()[attr_name] = obj
            __all__.append(attr_name)

# 兼容 CLI：仍可通过环境变量控制 run.py stress 默认 shape（WebUI 已改用平台选择）。
if os.getenv("LOCUST_ENABLE_SHAPE", "0") in {"1", "true", "TRUE", "yes", "on"}:
    selected_shape = os.getenv("LOCUST_SHAPE", "stage").strip().lower()
    if selected_shape == "stage_hold":
        __all__ = [n for n in __all__ if n != "StageShape"]
    else:
        __all__ = [n for n in __all__ if n != "StageHoldShape"]
