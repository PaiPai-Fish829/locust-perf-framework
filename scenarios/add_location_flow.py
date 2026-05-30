"""
登录 + 添加收货地址。

- on_start：登录（失败记 login 的 #Fails，不 raise，便于后续 task 继续打出失败）
- @task add_location：断言「收货地址信息已成功更新」
"""

from __future__ import annotations

from locust import HttpUser, between, task

from common import metrics  # noqa: F401
from common.user_session import UserSession
from config import settings
from tasks.add_location import add_location_task
from utils.parametrize import scenario_cases


class AddLocationFlowScenario(HttpUser):
    """登录会话 + 添加收货地址；参数化数据默认 users.yaml。"""

    host = settings.LOCUST_HOST
    wait_time = between(1, 2)
    parametrized = True
    default_data_file = "users.yaml"
    data_strategy = settings.DATA_STRATEGY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = UserSession(self.client)
        self.data = {}

    @scenario_cases()
    def on_start(self):
        self.session = UserSession.from_parametrize_data(self.client, self.data)

        if self.session.is_manual:
            self.session.apply_manual_token(self.data.get("token"))
            return

        self.session.login_once(self.data)

    @task(1)
    def add_location(self):
        add_location_task(self.client, self.session)
