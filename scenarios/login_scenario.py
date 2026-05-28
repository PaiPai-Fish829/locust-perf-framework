from locust import HttpUser, between

from common import metrics  # noqa: F401  # side-effect: 注册 /metrics 路由
from common.auth import login
from common.data_loader import load_csv_rows, load_json_rows
from config import settings
from tasks.login_task import login_task


class LoginScenario(HttpUser):
    host = settings.LOCUST_HOST
    wait_time = between(1, 2)
    tasks = [login_task]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = ""
        self.param_rows = []
        self._row_index = 0

    def on_start(self):
        # JMeter 痛点规避：登录后把 token 存在用户实例变量 self.token，
        # 后续请求天然可复用，无需跨线程共享变量。
        auth_info = login(self.client)
        self.token = auth_info.get("token", "")
        self.param_rows = self._load_param_rows()

    def _load_param_rows(self):
        if not settings.DATA_FILE:
            return []
        if settings.DATA_FILE.endswith(".csv"):
            return load_csv_rows(settings.DATA_FILE)
        if settings.DATA_FILE.endswith(".json"):
            return load_json_rows(settings.DATA_FILE)
        return []
