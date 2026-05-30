"""
登录 + 业务流程场景。

- on_start：参数化、会话初始化（登录仅一次）
- @task：编排接口调用；断言在各 ``tasks/*_task.py`` 内完成
"""

from __future__ import annotations

from typing import Any, Callable

from locust import HttpUser, between, task

from common import metrics  # noqa: F401
from common.user_session import UserSession
from config import settings
from utils.parametrize import scenario_cases
from tasks.add_location import add_location_task

TaskRunner = Callable[..., None]


class LoginScenario(HttpUser):
    host = settings.LOCUST_HOST
    wait_time = between(1, 2)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = UserSession(self.client)
        self.case = {"data": {}, "expvalue": {}}
        self.data: dict[str, Any] = {}
        self.expvalue: dict[str, Any] = {}

    @scenario_cases(settings.DATA_FILE, strategy=settings.DATA_STRATEGY)
    def on_start(self):
        self.session = UserSession.from_parametrize_data(self.client, self.data)

        if self.session.is_manual:
            self.session.apply_manual_token(self.data.get("token"))
            return

        self.session.login_once(self.data, self.expvalue)

    def _run_task(
        self,
        task_fn: TaskRunner,
        *,
        data: dict | None = None,
        expvalue: dict | None = None,
    ) -> None:
        task_fn(
            self.client,
            self.session,
            data if data is not None else self.data,
            expvalue if expvalue is not None else self.expvalue,
        )

    @task(1)
    def add_location(self):
        self._run_task(add_location_task)
