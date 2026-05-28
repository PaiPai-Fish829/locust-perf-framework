#!/usr/bin/env python
"""Unified CLI entrypoint for Locust runs."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
WATCH_EXTENSIONS = {".py"}

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import settings


def _shape_from_env(default_when_enabled: str, fallback: str) -> str:
    """
    兼容两套环境变量：
    - 新变量: LOCUST_SHAPE=none/stage/stage_hold
    - 旧变量: LOCUST_ENABLE_SHAPE=0/1
    """
    shape = os.getenv("LOCUST_SHAPE")
    if shape:
        return shape
    enable = os.getenv("LOCUST_ENABLE_SHAPE")
    if enable in {"1", "true", "TRUE", "yes", "on"}:
        return default_when_enabled
    return fallback


def _env_or_arg(env_name: str, arg_value, fallback):
    env_value = os.getenv(env_name)
    if env_value is not None and str(env_value).strip() != "":
        return env_value
    if arg_value is not None:
        return arg_value
    return fallback


def _resolve_locust_cmd() -> str:
    candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "locust.exe",
        PROJECT_ROOT / ".venv" / "bin" / "locust",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "locust"


def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("", port))
            return False
        except OSError:
            return True


def _should_watch(path: Path) -> bool:
    if path.suffix not in WATCH_EXTENSIONS:
        return False
    excluded_roots = {".venv", ".git", "__pycache__", "reports", ".pytest_cache"}
    return not any(part in excluded_roots for part in path.parts)


def _build_snapshot() -> dict[Path, int]:
    snapshot: dict[Path, int] = {}
    for file_path in PROJECT_ROOT.rglob("*"):
        if not file_path.is_file() or not _should_watch(file_path):
            continue
        try:
            snapshot[file_path] = file_path.stat().st_mtime_ns
        except OSError:
            continue
    return snapshot


def _run_with_reload(cmd: list[str]) -> int:
    print("自动重载已启用：检测到 .py 文件变更后将重启 Locust。")
    snapshot = _build_snapshot()
    process: subprocess.Popen[str] | None = None

    try:
        while True:
            process = subprocess.Popen(cmd, cwd=PROJECT_ROOT)
            while True:
                return_code = process.poll()
                if return_code is not None:
                    return return_code
                time.sleep(1.0)
                latest = _build_snapshot()
                if latest != snapshot:
                    print("检测到代码变更，正在重启 Locust WebUI ...")
                    snapshot = latest
                    process.terminate()
                    process.wait(timeout=10)
                    break
    except KeyboardInterrupt:
        if process and process.poll() is None:
            process.terminate()
        print("\n已停止。")
        return 130


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Locust unified CLI runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--host", default=os.getenv("LOCUST_HOST", settings.LOCUST_HOST), help="Target host")
    common.add_argument(
        "--locustfile",
        default="locustfile.py",
        help="Path to locust file",
    )

    shape_help = (
        "Shape mode: none(禁用), stage(基础阶梯), stage_hold(阶梯+峰值保持)。"
        "兼容旧值 0/1。"
    )

    load = subparsers.add_parser("load", parents=[common], help="WebUI debug mode")
    load.add_argument(
        "--web-port",
        type=int,
        default=int(os.getenv("LOCUST_WEB_PORT", str(settings.LOCUST_WEB_PORT))),
        help="WebUI port",
    )
    load.add_argument(
        "--shape",
        choices=("none", "stage", "stage_hold", "0", "1"),
        default=_shape_from_env(default_when_enabled="stage", fallback="none"),
        help=shape_help,
    )
    load.add_argument("--csv-prefix", default="reports/load", help="CSV output prefix")
    load_group = load.add_mutually_exclusive_group()
    load_group.add_argument(
        "--reload",
        dest="reload",
        action="store_true",
        default=bool(settings.LOCUST_WEB_RELOAD),
        help="Auto restart Locust when code changes",
    )
    load_group.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable auto reload behavior",
    )

    stress = subparsers.add_parser("stress", parents=[common], help="Headless stress mode")
    stress.add_argument("--users", type=int, default=int(os.getenv("LOCUST_USERS", str(settings.LOCUST_USERS))))
    stress.add_argument(
        "--spawn-rate",
        type=float,
        default=float(os.getenv("LOCUST_SPAWN_RATE", str(settings.LOCUST_SPAWN_RATE))),
    )
    stress.add_argument("--run-time", default=os.getenv("LOCUST_RUN_TIME", settings.LOCUST_RUN_TIME))
    stress.add_argument(
        "--shape",
        choices=("none", "stage", "stage_hold", "0", "1"),
        default=_shape_from_env(default_when_enabled=settings.SHAPE_DEFAULT, fallback=settings.SHAPE_DEFAULT),
        help=shape_help,
    )
    stress.add_argument("--csv-prefix", default="reports/stress", help="CSV output prefix")
    stress.add_argument(
        "--start-users",
        type=int,
        default=int(os.getenv("LOCUST_SHAPE_START_USERS", str(settings.SHAPE_START_USERS))),
        help="stage_hold: 起始用户数",
    )
    stress.add_argument(
        "--step-users",
        type=int,
        default=int(os.getenv("LOCUST_SHAPE_STEP_USERS", str(settings.SHAPE_STEP_USERS))),
        help="stage_hold: 每阶梯增加用户数",
    )
    stress.add_argument(
        "--step-duration",
        type=int,
        default=int(os.getenv("LOCUST_SHAPE_STEP_DURATION", str(settings.SHAPE_STEP_DURATION))),
        help="stage_hold: 每阶梯持续秒数",
    )
    stress.add_argument(
        "--peak-users",
        type=int,
        default=int(os.getenv("LOCUST_SHAPE_PEAK_USERS", str(settings.SHAPE_PEAK_USERS))),
        help="stage_hold: 峰值用户数",
    )
    stress.add_argument(
        "--peak-hold-time",
        type=int,
        default=int(os.getenv("LOCUST_SHAPE_PEAK_HOLD_TIME", str(settings.SHAPE_PEAK_HOLD_TIME))),
        help="stage_hold: 峰值保持秒数",
    )
    stress.add_argument(
        "--total-time-limit",
        type=int,
        default=int(os.getenv("LOCUST_SHAPE_TOTAL_TIME_LIMIT", str(settings.SHAPE_TOTAL_TIME_LIMIT))),
        help="stage_hold: 总时长上限，0 表示不设置",
    )

    return parser


def _run_locust(args: argparse.Namespace, passthrough: list[str]) -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    raw_shape = str(_env_or_arg("LOCUST_SHAPE", args.shape, settings.SHAPE_DEFAULT)).strip().lower()
    if raw_shape == "0":
        shape_enabled = "0"
        shape_name = "none"
    elif raw_shape == "1":
        shape_enabled = "1"
        shape_name = "stage"
    elif raw_shape == "none":
        shape_enabled = "0"
        shape_name = "none"
    elif raw_shape in {"stage", "stage_hold"}:
        shape_enabled = "1"
        shape_name = raw_shape
    else:
        raise ValueError(f"不支持的 shape: {args.shape}")

    os.environ["LOCUST_ENABLE_SHAPE"] = shape_enabled
    os.environ["LOCUST_SHAPE"] = shape_name
    os.environ["LOCUST_SHAPE_START_USERS"] = str(
        _env_or_arg("LOCUST_SHAPE_START_USERS", getattr(args, "start_users", None), settings.SHAPE_START_USERS)
    )
    os.environ["LOCUST_SHAPE_STEP_USERS"] = str(
        _env_or_arg("LOCUST_SHAPE_STEP_USERS", getattr(args, "step_users", None), settings.SHAPE_STEP_USERS)
    )
    os.environ["LOCUST_SHAPE_STEP_DURATION"] = str(
        _env_or_arg("LOCUST_SHAPE_STEP_DURATION", getattr(args, "step_duration", None), settings.SHAPE_STEP_DURATION)
    )
    os.environ["LOCUST_SHAPE_PEAK_USERS"] = str(
        _env_or_arg("LOCUST_SHAPE_PEAK_USERS", getattr(args, "peak_users", None), settings.SHAPE_PEAK_USERS)
    )
    os.environ["LOCUST_SHAPE_PEAK_HOLD_TIME"] = str(
        _env_or_arg(
            "LOCUST_SHAPE_PEAK_HOLD_TIME",
            getattr(args, "peak_hold_time", None),
            settings.SHAPE_PEAK_HOLD_TIME,
        )
    )
    os.environ["LOCUST_SHAPE_TOTAL_TIME_LIMIT"] = str(
        _env_or_arg(
            "LOCUST_SHAPE_TOTAL_TIME_LIMIT",
            getattr(args, "total_time_limit", None),
            settings.SHAPE_TOTAL_TIME_LIMIT,
        )
    )

    cmd = [
        _resolve_locust_cmd(),
        "-f",
        args.locustfile,
        "--host",
        args.host,
        f"--csv={args.csv_prefix}",
        "--csv-full-history",
    ]

    if args.command == "load":
        if _is_port_in_use(args.web_port):
            print(
                f"端口 {args.web_port} 已被占用。请先停止当前占用进程，"
                "或在根目录 locust-config.yaml 中调整当前环境的 locust_web_port。"
            )
            return 1
        cmd.extend(["--web-port", str(args.web_port)])
        print(f"WebUI URL: http://localhost:{args.web_port}")
        if shape_enabled == "1":
            print(f"当前 shape: {shape_name}（WebUI 并发输入框会由 Locust 自动禁用）")
    else:
        cmd.extend(
            [
                "--headless",
                "--users",
                str(args.users),
                "--spawn-rate",
                str(args.spawn_rate),
                "--run-time",
                args.run_time,
            ]
        )
        if shape_enabled == "1":
            print(f"当前 shape: {shape_name}")

    cmd.extend(passthrough)
    print("执行命令:", " ".join(cmd))
    if args.command == "load" and args.reload:
        return _run_with_reload(cmd)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=False)
    return int(result.returncode)


def main() -> int:
    parser = _build_parser()
    args, passthrough = parser.parse_known_args()
    return _run_locust(args, passthrough)


if __name__ == "__main__":
    sys.exit(main())
