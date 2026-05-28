import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "locust-config.json"


def _load_root_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"未找到配置文件: {CONFIG_FILE}")

    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        config = json.load(f)

    if not isinstance(config, dict):
        raise ValueError("根配置文件格式错误，顶层必须是 JSON Object。")
    return config


def _require_text(source: dict[str, Any], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str):
        raise ValueError(f"配置项 `{key}` 必须是字符串。")
    return value


def _require_int(source: dict[str, Any], key: str) -> int:
    value = source.get(key)
    if isinstance(value, bool):
        raise ValueError(f"配置项 `{key}` 必须是整数。")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        return int(value)
    raise ValueError(f"配置项 `{key}` 必须是整数。")


def _require_bool(source: dict[str, Any], key: str) -> bool:
    value = source.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"配置项 `{key}` 必须是布尔值。")


_ROOT_CONFIG = _load_root_config()
_ENVIRONMENTS = _ROOT_CONFIG.get("environments")
if not isinstance(_ENVIRONMENTS, dict) or not _ENVIRONMENTS:
    raise ValueError("配置文件缺少 `environments`，或其内容为空。")

CURRENT_ENV = os.getenv("LOCUST_ENV") or _require_text(_ROOT_CONFIG, "active_env")
_CURRENT_ENV_CONFIG = _ENVIRONMENTS.get(CURRENT_ENV)
if not isinstance(_CURRENT_ENV_CONFIG, dict):
    raise ValueError(f"环境 `{CURRENT_ENV}` 不存在于 `environments` 中。")

LOCUST_HOST = _require_text(_CURRENT_ENV_CONFIG, "locust_host")
LOCUST_USERS = _require_int(_CURRENT_ENV_CONFIG, "locust_users")
LOCUST_SPAWN_RATE = _require_int(_CURRENT_ENV_CONFIG, "locust_spawn_rate")
LOCUST_RUN_TIME = _require_text(_CURRENT_ENV_CONFIG, "locust_run_time")
LOCUST_WEB_PORT = _require_int(_CURRENT_ENV_CONFIG, "locust_web_port")
LOCUST_WEB_RELOAD = _require_bool(_CURRENT_ENV_CONFIG, "locust_web_reload")

LOGIN_PATH = _require_text(_CURRENT_ENV_CONFIG, "login_path")
LOGIN_USERNAME = _require_text(_CURRENT_ENV_CONFIG, "login_username")
LOGIN_PASSWORD = _require_text(_CURRENT_ENV_CONFIG, "login_password")
DATA_FILE = _require_text(_CURRENT_ENV_CONFIG, "data_file")
