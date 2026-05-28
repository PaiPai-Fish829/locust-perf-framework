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

    load = subparsers.add_parser("load", parents=[common], help="WebUI debug mode")
    load.add_argument(
        "--web-port",
        type=int,
        default=int(os.getenv("LOCUST_WEB_PORT", str(settings.LOCUST_WEB_PORT))),
        help="WebUI port",
    )
    load.add_argument(
        "--shape",
        choices=("0", "1"),
        default=os.getenv("LOCUST_ENABLE_SHAPE", "0"),
        help="Enable LoadTestShape via LOCUST_ENABLE_SHAPE",
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
        choices=("0", "1"),
        default=os.getenv("LOCUST_ENABLE_SHAPE", "1"),
        help="Enable LoadTestShape via LOCUST_ENABLE_SHAPE",
    )
    stress.add_argument("--csv-prefix", default="reports/stress", help="CSV output prefix")

    return parser


def _run_locust(args: argparse.Namespace, passthrough: list[str]) -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["LOCUST_ENABLE_SHAPE"] = args.shape

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
                "或在 config/settings.py 中调整 LOCUST_WEB_PORT。"
            )
            return 1
        cmd.extend(["--web-port", str(args.web_port)])
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
