from locust import LoadTestShape


class StageShape(LoadTestShape):
    """
    每 30 秒增加 10 用户，直到 100 用户。
    """

    step_time = 30
    step_users = 10
    spawn_rate = 10
    max_users = 100

    def tick(self):
        run_time = self.get_run_time()
        current_step = int(run_time // self.step_time) + 1
        user_count = current_step * self.step_users
        if user_count > self.max_users:
            return None
        return user_count, self.spawn_rate
