import os


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        return int(value)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


LOCUST_HOST = os.getenv("LOCUST_HOST", "http://192.168.47.129:80")
LOCUST_USERS = _get_int("LOCUST_USERS", 10)
LOCUST_SPAWN_RATE = _get_int("LOCUST_SPAWN_RATE", 10)
LOCUST_RUN_TIME = os.getenv("LOCUST_RUN_TIME", "5m")
LOCUST_WEB_PORT = _get_int("LOCUST_WEB_PORT", 8089)
LOCUST_WEB_RELOAD = _get_bool("LOCUST_WEB_RELOAD", True)

LOGIN_PATH = os.getenv("LOGIN_PATH", "/ecshop/user.php")
LOGIN_USERNAME = os.getenv("LOGIN_USERNAME", "test")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "123456")

DATA_FILE = os.getenv("DATA_FILE", "")
