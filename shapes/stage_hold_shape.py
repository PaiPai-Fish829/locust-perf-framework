from __future__ import annotations

import math

from utils.configurable_shape import ConfigurableShape

SHAPE_DEFAULTS = {
    "start_users": 10,
    "step_users": 10,
    "step_duration": 30,
    "peak_users": 100,
    "peak_hold_time": 60,
    "total_time_limit": 0,
    "spawn_rate": 10,
}

SHAPE_PARAMS = [
    {"name": "start_users", "label": "起始用户数", "min": 1, "max": 100000, "unit": ""},
    {"name": "step_users", "label": "每阶梯增加用户数", "min": 1, "max": 10000, "unit": ""},
    {"name": "step_duration", "label": "阶梯时长", "min": 1, "max": 3600, "unit": "秒"},
    {"name": "peak_users", "label": "峰值用户数", "min": 1, "max": 100000, "unit": ""},
    {"name": "peak_hold_time", "label": "峰值保持时间", "min": 0, "max": 86400, "unit": "秒"},
]


class StageHoldShape(ConfigurableShape):
    """
    阶梯 + 峰值保持压测模型。

    行为：
    1) 从 start_users 开始；
    2) 每 step_duration 秒增加 step_users，直到 peak_users；
    3) 达到峰值后继续保持 peak_hold_time 秒；
    4) 达到停止条件后返回 None，Locust 自动结束。
    """

    SHAPE_DEFAULTS = SHAPE_DEFAULTS
    SHAPE_PARAMS = SHAPE_PARAMS

    def tick(self):
        run_time = self.get_run_time()

        if self.total_time_limit > 0 and run_time >= self.total_time_limit:
            return None

        if self.step_duration <= 0:
            raise ValueError("step_duration 必须大于 0")
        if self.step_users <= 0:
            raise ValueError("step_users 必须大于 0")
        if self.peak_users <= 0:
            raise ValueError("peak_users 必须大于 0")

        base_users = max(1, min(self.start_users, self.peak_users))
        growth_span = max(0, self.peak_users - base_users)
        growth_steps = 0 if growth_span == 0 else math.ceil(growth_span / self.step_users)
        growth_time = growth_steps * self.step_duration

        if run_time < growth_time:
            current_step = int(run_time // self.step_duration)
            users = min(self.peak_users, base_users + current_step * self.step_users)
            return users, self.spawn_rate

        peak_end_time = growth_time + max(0, self.peak_hold_time)
        if run_time < peak_end_time:
            return self.peak_users, self.spawn_rate

        return None
