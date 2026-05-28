from __future__ import annotations

import math
import os

from locust import LoadTestShape

from config import settings


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


class StageHoldShape(LoadTestShape):
    """
    阶梯 + 峰值保持压测模型。

    行为：
    1) 从 start_users 开始；
    2) 每 step_duration 秒增加 step_users，直到 peak_users；
    3) 达到峰值后继续保持 peak_hold_time 秒；
    4) 达到停止条件后返回 None，Locust 自动结束。

    扩展建议：
    - 如果需要“每个阶梯内再线性爬升”，可把 tick 的阶梯值改为函数插值；
    - 如果需要回落阶段，可在峰值保持后追加下降段逻辑。
    """

    start_users = _env_int("LOCUST_SHAPE_START_USERS", settings.SHAPE_START_USERS)
    step_users = _env_int("LOCUST_SHAPE_STEP_USERS", settings.SHAPE_STEP_USERS)
    step_duration = _env_int("LOCUST_SHAPE_STEP_DURATION", settings.SHAPE_STEP_DURATION)
    peak_users = _env_int("LOCUST_SHAPE_PEAK_USERS", settings.SHAPE_PEAK_USERS)
    peak_hold_time = _env_int("LOCUST_SHAPE_PEAK_HOLD_TIME", settings.SHAPE_PEAK_HOLD_TIME)
    total_time_limit = _env_int("LOCUST_SHAPE_TOTAL_TIME_LIMIT", settings.SHAPE_TOTAL_TIME_LIMIT)
    spawn_rate = max(1, _env_int("LOCUST_SPAWN_RATE", settings.LOCUST_SPAWN_RATE))

    def tick(self):
        run_time = self.get_run_time()

        # 总时长限制优先级最高（满足后立即停止）。
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
