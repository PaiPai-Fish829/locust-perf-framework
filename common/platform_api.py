"""管理平台 API：扫描 scenarios/ 与 shapes/ 目录，并提供带策略参数的启动接口。"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
from typing import Any

from flask import jsonify, request
from locust import events

from utils.configurable_shape import ConfigurableShape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = PROJECT_ROOT / "scenarios"
SHAPES_DIR = PROJECT_ROOT / "shapes"


def _base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def _parse_scenario_module(path: Path) -> list[dict]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    results: list[dict] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if "HttpUser" not in _base_names(node):
            continue
        results.append(
            {
                "class_name": node.name,
                "description": (ast.get_docstring(node) or "").strip(),
            }
        )
    return results


def list_scenario_files() -> list[dict]:
    items: list[dict] = []
    if not SCENARIOS_DIR.is_dir():
        return items
    for path in sorted(SCENARIOS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        classes = _parse_scenario_module(path)
        if not classes:
            continue
        primary = classes[0]
        items.append(
            {
                "id": path.stem,
                "filename": path.name,
                "class_name": primary["class_name"],
                "description": primary["description"],
            }
        )
    return items


def _iter_shape_classes() -> list[tuple[str, type[ConfigurableShape]]]:
    found: list[tuple[str, type[ConfigurableShape]]] = []
    if not SHAPES_DIR.is_dir():
        return found
    for path in sorted(SHAPES_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module = importlib.import_module(f"shapes.{path.stem}")
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, ConfigurableShape)
                and obj is not ConfigurableShape
                and not getattr(obj, "abstract", True)
            ):
                found.append((path.stem, obj))
    return found


def list_shape_files() -> list[dict]:
    items: list[dict] = []
    for shape_id, shape_cls in _iter_shape_classes():
        items.append(
            {
                "id": shape_id,
                "filename": f"{shape_id}.py",
                "class_name": shape_cls.__name__,
                "description": (shape_cls.__doc__ or "").strip(),
                "params": shape_cls.param_schema(),
            }
        )
    return items


def _parse_shape_params(raw: Any) -> dict[str, int | float]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        parsed = json.loads(raw)
    else:
        parsed = raw
    if not isinstance(parsed, dict):
        return {}
    result: dict[str, int | float] = {}
    for key, value in parsed.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            result[str(key)] = value
    return result


def _run_platform_swarm(environment, web_ui, payload: dict[str, Any]):
    """直接启动压测，避免 test_request_context 转发 /swarm 时丢失 form 字段。"""
    import gevent
    from locust.log import greenlet_exception_logger
    from locust.util.timespan import parse_timespan

    logger = greenlet_exception_logger(__import__("logging").getLogger("locust.web"))
    host = environment.host

    environment._pending_shape_params = _parse_shape_params(payload.get("shape_params"))

    user_class_names = payload.get("user_classes") or []
    if user_class_names and environment.available_user_classes:
        selected = {
            name: cls
            for name, cls in environment.available_user_classes.items()
            if name in user_class_names
        }
        if selected:
            web_ui._update_user_classes(selected)

    shape_name = payload.get("shape_class") or "Default"
    try:
        if shape_name == "Default":
            web_ui._update_shape_class(None)
        else:
            web_ui._update_shape_class(shape_name)
    except KeyError:
        environment._pending_shape_params = None
        return jsonify(
            {
                "success": False,
                "message": f"未知策略 shape_class: {shape_name}",
                "host": host,
            }
        )

    if payload.get("host"):
        environment.host = str(payload["host"]).replace("<", "").replace(">", "")

    run_time = None
    if payload.get("run_time"):
        try:
            run_time = parse_timespan(str(payload["run_time"]))
        except ValueError:
            return jsonify(
                {
                    "success": False,
                    "message": "run_time 格式无效，示例: 5m, 30s, 1h",
                    "host": environment.host,
                }
            )

    if environment.runner is None:
        return jsonify({"success": False, "message": "No runner", "host": environment.host})

    if environment.shape_class is not None:
        environment.runner.start_shape()
        if run_time:
            gevent.spawn_later(run_time, web_ui._stop_runners).link_exception(
                logger
            )
        return jsonify(
            {
                "success": True,
                "message": f"Swarming started using shape class '{type(environment.shape_class).__name__}'",
                "host": environment.host,
            }
        )

    user_count = payload.get("user_count")
    spawn_rate = payload.get("spawn_rate")
    if user_count is None or spawn_rate is None:
        return jsonify(
            {
                "success": False,
                "message": "Missing user_count or spawn_rate from /swarm request",
                "host": environment.host,
            }
        )

    if web_ui._swarm_greenlet is not None:
        web_ui._swarm_greenlet.kill(block=True)
        web_ui._swarm_greenlet = None

    web_ui._swarm_greenlet = gevent.spawn(
        environment.runner.start, int(user_count), float(spawn_rate)
    )
    web_ui._swarm_greenlet.link_exception(logger)

    response_data: dict[str, Any] = {
        "success": True,
        "message": "Swarming started",
        "host": environment.host,
    }
    if run_time:
        gevent.spawn_later(run_time, web_ui._stop_runners).link_exception(
            logger
        )
        response_data["run_time"] = run_time
    return jsonify(response_data)


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    if environment.web_ui is None:
        return

    web_ui = environment.web_ui
    original_update_shape = web_ui._update_shape_class

    def _update_shape_class_with_params(shape_class_name: str | None) -> None:
        original_update_shape(shape_class_name)
        pending = getattr(environment, "_pending_shape_params", None)
        shape = environment.shape_class
        if pending is not None and shape is not None and hasattr(shape, "apply_params"):
            shape.apply_params(pending)
        environment._pending_shape_params = None

    web_ui._update_shape_class = _update_shape_class_with_params

    @environment.web_ui.app.route("/platform/scenarios")
    def platform_scenarios():
        return jsonify({"scenarios": list_scenario_files()})

    @environment.web_ui.app.route("/platform/shapes")
    def platform_shapes():
        return jsonify({"shapes": list_shape_files()})

    @environment.web_ui.app.route("/platform/stats/history")
    def platform_stats_history():
        """返回 Locust 服务端 stats.history，与原生 WebUI 图表数据源一致。"""
        runner = environment.runner
        if runner is None:
            return jsonify({"history": []})
        return jsonify({"history": runner.stats.history})

    @environment.web_ui.app.route("/platform/swarm", methods=["POST"])
    def platform_swarm():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            payload = request.form.to_dict(flat=True)
            user_classes = request.form.getlist("user_classes")
            if user_classes:
                payload["user_classes"] = user_classes
            shape_params_raw = payload.get("shape_params")
            if isinstance(shape_params_raw, str) and shape_params_raw.strip():
                try:
                    payload["shape_params"] = json.loads(shape_params_raw)
                except json.JSONDecodeError:
                    return jsonify({"success": False, "message": "shape_params 不是合法 JSON"}), 400

        return _run_platform_swarm(environment, web_ui, payload)
