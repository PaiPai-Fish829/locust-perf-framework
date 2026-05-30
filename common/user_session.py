"""
虚拟用户会话：登录成功后才允许业务接口。
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Mapping

from tasks.login_task import login_task


class AuthMode(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


class UserSession:
    def __init__(
        self,
        client: Any,
        *,
        mode: str | AuthMode = AuthMode.AUTO,
        token: str | None = None,
    ) -> None:
        self.client = client
        self.mode = AuthMode(mode) if isinstance(mode, str) else mode
        self.token = (token or "").strip()
        self.php_sessid = ""
        self.ready = False
        self.login_ok = False

    @classmethod
    def from_parametrize_data(cls, client: Any, data: Mapping[str, Any] | None) -> UserSession:
        data = data or {}
        token = str(data.get("token") or os.getenv("LOCUST_MANUAL_TOKEN") or "").strip()
        mode_raw = str(
            data.get("auth_mode") or os.getenv("LOCUST_AUTH_MODE") or ""
        ).strip().lower()

        if mode_raw in {AuthMode.MANUAL.value, "manual"}:
            mode = AuthMode.MANUAL
        elif mode_raw in {AuthMode.AUTO.value, "auto"}:
            mode = AuthMode.AUTO
        else:
            mode = AuthMode.MANUAL if token else AuthMode.AUTO

        return cls(client, mode=mode, token=token)

    @property
    def is_manual(self) -> bool:
        return self.mode == AuthMode.MANUAL

    def login_once(self, login_data: Mapping[str, Any] | None = None) -> bool:
        if self.is_manual:
            raise RuntimeError("manual 模式不应调用 login_once")
        self.login_ok = login_task(self.client, dict(login_data or {}))
        if self.login_ok:
            self.sync_from_client()
            self.ready = True
        else:
            self.ready = False
        return self.login_ok

    def apply_manual_token(self, token: str | None = None) -> None:
        value = (token or self.token or "").strip()
        if not value:
            raise ValueError("manual 模式需要非空 token")
        self.token = value
        self.mode = AuthMode.MANUAL
        self.login_ok = True
        self.ready = True

    def sync_from_client(self) -> None:
        cookies = getattr(self.client, "cookies", None)
        if cookies is None:
            return
        for key in ("token", "ECSCP_ID", "PHPSESSID", "ECS_ID"):
            value = cookies.get(key)
            if value:
                if key in ("PHPSESSID", "ECS_ID"):
                    self.php_sessid = str(value)
                elif key == "token" or not self.token:
                    self.token = str(value)

    def php_session_id(self) -> str:
        if self.php_sessid:
            return self.php_sessid
        cookies = getattr(self.client, "cookies", None)
        if cookies is not None:
            for key in ("PHPSESSID", "ECS_ID"):
                value = cookies.get(key)
                if value:
                    return str(value)
        return ""

    def require_logged_in(self) -> None:
        if not self.login_ok:
            raise RuntimeError("登录未成功，跳过业务请求")

    def require_ready(self) -> None:
        if not self.ready:
            raise RuntimeError("会话未就绪")

    def headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        self.require_logged_in()
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(dict(extra))
        return headers

    def as_dict(self) -> dict[str, str]:
        return {"token": self.token, "mode": self.mode.value, "ready": str(self.ready)}
