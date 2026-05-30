"""
仅压测登录接口。

- on_start：绑定参数化账号
- @task login：每次循环调用登录接口（不依赖会话复用）
"""

from __future__ import annotations

from locust import HttpUser, between, task

from common import metrics  # noqa: F401
from config import settings
from tasks.login_task import login_task
from utils.parametrize import scenario_cases


class LoginScenario(HttpUser):
    """登录接口压测；参数化数据默认 users.yaml。"""

    host = settings.LOCUST_HOST
    wait_time = between(1, 2)
    parametrized = True
    default_data_file = "users.yaml"
    data_strategy = settings.DATA_STRATEGY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = {}

    @scenario_cases()
    def on_start(self):
        """仅绑定 data，供 login task 使用。"""
        return

    @task(1)
    def login(self):
        login_task(self.client, self.data)
