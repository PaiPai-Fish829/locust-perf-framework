from locust import HttpUser, between

from common import metrics  # noqa: F401  # side-effect: 注册 /metrics 路由
from common.auth import login
from common.data_loader import assign_user_row
from config import settings
from tasks.login_task import login_task


class LoginScenario(HttpUser):
    host = settings.LOCUST_HOST
    wait_time = between(1, 2)
    tasks = [login_task]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = ""
        self.user_data = {}

    def on_start(self):
        # JMeter 痛点规避：登录后把 token 存在用户实例变量 self.token，
        # 后续请求天然可复用，无需跨线程共享变量。
        auth_info = login(self.client)
        self.token = auth_info.get("token", "")
        # 每个虚拟用户在 on_start 分配一条稳定数据，避免每次 task 都重新读文件。
        if settings.DATA_FILE:
            self.user_data = assign_user_row(
                self,
                file_name=settings.DATA_FILE,
                strategy=settings.DATA_STRATEGY,
            )
