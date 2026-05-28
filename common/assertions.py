def assert_status_ok(status_code: int, response_text: str) -> None:
    if status_code != 200:
        raise AssertionError(f"HTTP {status_code}: {response_text[:200]}")
