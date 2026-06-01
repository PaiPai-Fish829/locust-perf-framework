"""POST /ecshop/user.php?act=act_edit_address — 添加/编辑收货地址。"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from utils.api_payload import build_payload

if TYPE_CHECKING:
    from common.user_session import UserSession

PATH = "/ecshop/user.php"
REQUEST_NAME = "POST /ecshop/user.php add_address"

HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}


class AddLocationPayload(TypedDict):
    country: str
    province: str
    city: str
    district: str
    consignee: str
    email: str
    address: str
    zipcode: str
    tel: str
    mobile: str
    sign_building: str
    best_time: str
    submit: str
    act: str
    address_id: str


DEFAULT_PAYLOAD: AddLocationPayload = {
    "country": "1",
    "province": "20",
    "city": "233",
    "district": "2416",
    "consignee": "张三",
    "email": "123456@qq.com",
    "address": "时尚广场",
    "zipcode": "11111111111",
    "tel": "11111111111",
    "mobile": "11111111111",
    "sign_building": "11111111111",
    "best_time": "11111111111",
    "submit": "确认修改",
    "act": "act_edit_address",
    "address_id": "5",
}


def build_request_headers(session: UserSession) -> dict[str, str]:
    headers = dict(HEADERS)
    session_id = session.get_session_id()
    if session_id:
        headers["session"] = f"session_id={session_id}"
    return headers


def add_location_task(client, session: UserSession, data: dict | None = None) -> bool:
    with client.post(
        PATH,
        data=build_payload(DEFAULT_PAYLOAD, data),
        headers=build_request_headers(session),
        name=REQUEST_NAME,
        catch_response=True,
    ) as response:
        if "收货地址信息已成功更新" not in response.text:
            response.failure("正文不含「收货地址信息已成功更新」")
            return False
        response.success()
        return True
