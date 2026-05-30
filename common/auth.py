"""兼容入口，请改用 ``UserSession`` + ``tasks.login_task``。"""

from __future__ import annotations

from typing import Any, Dict

from common.user_session import UserSession


def login(client, data: dict | None = None) -> Dict[str, str]:
    session = UserSession.from_parametrize_data(client, data or {})
    if session.is_manual:
        session.apply_manual_token()
    else:
        session.login_once(data)
    return session.as_dict()
