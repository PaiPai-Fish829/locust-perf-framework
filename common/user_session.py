"""
虚拟用户会话（项目自定义类，不是 requests.Session）。

Locust 的 ``HttpUser.client`` 会在登录后自动保存 Cookie；本类在此基础上缓存
登录态，供业务 task 取 token / 会话 ID。

- **ECShop（PHP）**：登录后常见 ``ECS_ID`` / ``PHPSESSID``，部分接口还需自定义头
  ``session: session_id=...``（见 ``tasks/add_location.py``）
- **其他后端**：构造时传入 ``session_cookie_keys``，或用手动 token / JWT（``headers()``）
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Mapping, Sequence

from tasks.login_task import login_task

# 默认按 ECShop 习惯；Java 等可改为 ("JSESSIONID",) 或空元组（仅靠 client 自动带 Cookie）
DEFAULT_SESSION_COOKIE_KEYS: tuple[str, ...] = ("ECS_ID", "PHPSESSID", "ECSCP_ID")
DEFAULT_TOKEN_COOKIE_KEYS: tuple[str, ...] = ("token",)


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
        session_cookie_keys: Sequence[str] | None = None,
        token_cookie_keys: Sequence[str] | None = None,
    ) -> None:
        self.client = client
        self.mode = AuthMode(mode) if isinstance(mode, str) else mode
        self.token = (token or "").strip()
        self._session_cookie_keys = tuple(session_cookie_keys or DEFAULT_SESSION_COOKIE_KEYS)
        self._token_cookie_keys = tuple(token_cookie_keys or DEFAULT_TOKEN_COOKIE_KEYS)
        self._session_id = ""
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
        """从 Locust client 的 Cookie  jar 同步 token / 会话 ID。"""
        cookies = getattr(self.client, "cookies", None)
        if cookies is None:
            return
        for key in self._token_cookie_keys:
            value = cookies.get(key)
            if value and (key == "token" or not self.token):
                self.token = str(value)
        for key in self._session_cookie_keys:
            value = cookies.get(key)
            if value:
                self._session_id = str(value)
                return

    def get_session_id(self) -> str:
        """
        返回当前虚拟用户的会话标识（来自登录后 Cookie 或缓存）。

        与 requests 无关：requests/Locust 不会提供 ``get_session_id``，只维护 Cookie；
        本方法按 ``session_cookie_keys`` 从 Cookie 中读取。无匹配时返回空字符串。
        """
        if self._session_id:
            return self._session_id
        cookies = getattr(self.client, "cookies", None)
        if cookies is not None:
            for key in self._session_cookie_keys:
                value = cookies.get(key)
                if value:
                    return str(value)
        return ""

    def php_session_id(self) -> str:
        """兼容旧名；等价于 ``get_session_id()``（本项目最初针对 PHP/ECShop）。"""
        return self.get_session_id()

    def require_logged_in(self) -> None:
        if not self.login_ok:
            raise RuntimeError("登录未成功，跳过业务请求")

    def require_ready(self) -> None:
        if not self.ready:
            raise RuntimeError("会话未就绪")

    def headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        """JWT / Bearer 等：在 task 里 ``client.post(..., headers=session.headers())``。"""
        self.require_logged_in()
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(dict(extra))
        return headers

    def as_dict(self) -> dict[str, str]:
        return {
            "token": self.token,
            "session_id": self.get_session_id(),
            "mode": self.mode.value,
            "ready": str(self.ready),
        }
