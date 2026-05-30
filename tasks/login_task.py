from __future__ import annotations

from typing import Any, Mapping, TypedDict

from utils.api_assert import assert_http_response
from utils.api_payload import build_payload

PATH = "/ecshop/user.php"
REQUEST_NAME = "POST /ecshop/user.php login"

HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}

class LoginPayload(TypedDict):
    username: str
    password: str
    act: str
    back_act: str
    submit: str

DEFAULT_PAYLOAD: LoginPayload = {
    "username": "test",
    "password": "123456",
    "act": "act_login",
    "back_act": "./index.php",
    "submit": "1",
}

def build_request_headers(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    headers = dict(HEADERS)
    if extra:
        headers.update(dict(extra))
    return headers


def login_task(
    client,
    data: dict | None = None,
    expvalue: Mapping[str, Any] | None = None,
) -> None:
    with client.post(
        PATH,
        data=build_payload(DEFAULT_PAYLOAD, data),
        headers=build_request_headers(),
        name=REQUEST_NAME,
        catch_response=True,
    ) as response:
        assert_http_response(response, expvalue, REQUEST_NAME)
