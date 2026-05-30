"""
虚拟用户会话：统一管理 token / Cookie / 鉴权头。

两种模式：
- ``auto``：scenario 在 ``on_start`` 调用 ``login_task`` 一次（断言在接口层）
- ``manual``：使用 ``data.token`` 或 ``LOCUST_MANUAL_TOKEN``
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

    @property
    def is_auto(self) -> bool:
        return self.mode == AuthMode.AUTO

    def login_once(
        self,
        login_data: Mapping[str, Any] | None = None,
        expvalue: Mapping[str, Any] | None = None,
    ) -> None:
        """自动模式：执行登录接口（含断言），并同步 Cookie。"""
        if self.is_manual:
            raise RuntimeError("manual 模式不应调用 login_once")
        login_task(self.client, dict(login_data or {}), expvalue)
        self.sync_from_client()

    def apply_manual_token(self, token: str | None = None) -> None:
        value = (token or self.token or "").strip()
        if not value:
            raise ValueError("manual 模式需要非空 token（data.token 或 LOCUST_MANUAL_TOKEN）")
        self.token = value
        self.mode = AuthMode.MANUAL
        self.ready = True

    def sync_from_client(self) -> None:
        cookies = getattr(self.client, "cookies", None)
        if cookies is None:
            return
        for key in ("token", "ECSCP_ID", "PHPSESSID"):
            value = cookies.get(key)
            if value:
                if key == "PHPSESSID":
                    self.php_sessid = str(value)
                elif key == "token" or not self.token:
                    self.token = str(value)
        self.ready = True

    def php_session_id(self) -> str:
        """ecshop 等 PHP 站点登录后常用 PHPSESSID，供业务接口 session 头使用。"""
        if self.php_sessid:
            return self.php_sessid
        cookies = getattr(self.client, "cookies", None)
        if cookies is not None:
            value = cookies.get("PHPSESSID")
            if value:
                return str(value)
        return ""

    def require_ready(self) -> None:
        if not self.ready:
            raise RuntimeError("会话未初始化：请先在 scenario.on_start 完成登录或注入 token")

    def headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        self.require_ready()
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(dict(extra))
        return headers

    def as_dict(self) -> dict[str, str]:
        return {"token": self.token, "mode": self.mode.value, "ready": str(self.ready)}
