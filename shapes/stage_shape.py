from utils.configurable_shape import ConfigurableShape

SHAPE_DEFAULTS = {
    "step_time": 30,
    "step_users": 10,
    "spawn_rate": 10,
    "max_users": 100,
}

SHAPE_PARAMS = [
    {"name": "step_time", "label": "阶梯间隔", "min": 1, "max": 3600, "unit": "秒"},
    {"name": "step_users", "label": "每阶梯增加用户数", "min": 1, "max": 10000, "unit": ""},
    {"name": "spawn_rate", "label": "孵化率", "min": 1, "max": 1000, "unit": "users/秒"},
    {"name": "max_users", "label": "最大用户数", "min": 1, "max": 100000, "unit": ""},
]


class StageShape(ConfigurableShape):
    """
    每 30 秒增加 10 用户，直到 100 用户。
    """

    SHAPE_DEFAULTS = SHAPE_DEFAULTS
    SHAPE_PARAMS = SHAPE_PARAMS

    def tick(self):
        run_time = self.get_run_time()
        current_step = int(run_time // self.step_time) + 1
        user_count = current_step * self.step_users
        if user_count > self.max_users:
            return None
        return user_count, self.spawn_rate
