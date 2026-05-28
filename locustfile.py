import os

from scenarios.login_scenario import LoginScenario

__all__ = ["LoginScenario"]

# Locust 特性：一旦定义了 LoadTestShape，WebUI 的 users/spawn rate/run time 输入框会被禁用。
# 通过环境变量控制是否启用 shape，默认关闭，方便在 WebUI 手工输入参数。
if os.getenv("LOCUST_ENABLE_SHAPE", "0") in {"1", "true", "TRUE", "yes", "on"}:
    from shapes.stage_shape import StageShape

    __all__.append("StageShape")
