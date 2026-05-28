from typing import Dict

from locust.clients import ResponseContextManager

from config import settings
from common.assertions import assert_status_ok


def login(client) -> Dict[str, str]:
    payload = {
        "username": settings.LOGIN_USERNAME,
        "password": settings.LOGIN_PASSWORD,
        "act": "act_login",
        "back_act": "./index.php",
        "submit": "1",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    with client.post(
        settings.LOGIN_PATH,
        data=payload,
        headers=headers,
        name="POST /ecshop/user.php login",
        catch_response=True,
    ) as response:
        response = response  # type: ResponseContextManager
        assert_status_ok(response.status_code, response.text)
        response.success()

    # JMeter 常见痛点：线程间变量难传。Locust 中每个用户对象有独立实例变量，
    # 这里统一返回 token/cookie 信息，供 on_start 存到 self.token。
    token = client.cookies.get("token", "")
    return {"token": token}
