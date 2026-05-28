from locust import task

from config import settings
from tasks.login_config import LOGIN_PASSWORD, LOGIN_PATH, LOGIN_USERNAME


def build_login_payload(user) -> dict:
    # JMeter 参数化痛点：这里支持从 CSV/JSON 覆盖默认账号，实现数据驱动。
    if user.param_rows:
        row = user.param_rows[user._row_index % len(user.param_rows)]
        user._row_index += 1
        return {
            "username": row.get("username", LOGIN_USERNAME),
            "password": row.get("password", LOGIN_PASSWORD),
            "act": row.get("act", "act_login"),
            "back_act": row.get("back_act", "./index.php"),
            "submit": row.get("submit", "1"),
        }
    return {
        "username": LOGIN_USERNAME,
        "password": LOGIN_PASSWORD,
        "act": "act_login",
        "back_act": "./index.php",
        "submit": "1",
    }


@task
def login_task(user):
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = build_login_payload(user)
    if user.token:
        headers["Authorization"] = f"Bearer {user.token}"

    # 请求写法与 requests 一致：headers、params、json/data 均可直接传。
    with user.client.post(
        LOGIN_PATH,
        data=payload,
        headers=headers,
        name="POST /ecshop/user.php login",
        catch_response=True,
    ) as response:
        if response.status_code == 200:
            response.success()
        else:
            response.failure(f"HTTP {response.status_code}")
