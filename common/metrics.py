from flask import Response
from locust import events
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

REQUEST_TOTAL = Counter("locust_request_total", "Total requests seen by Locust")
FAILURE_TOTAL = Counter("locust_failure_total", "Total failed requests seen by Locust")
RECEIVED_BYTES_TOTAL = Counter(
    "locust_received_bytes_total",
    "Total received response bytes from all requests",
)
SENT_BYTES_TOTAL = Counter(
    "locust_sent_bytes_total",
    "Total sent request bytes from all requests",
)
CURRENT_RPS = Gauge("locust_current_rps", "Current requests per second")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, exception, **kwargs):
    REQUEST_TOTAL.inc()
    if exception:
        FAILURE_TOTAL.inc()
    if response_length:
        RECEIVED_BYTES_TOTAL.inc(response_length)

    # request body 字节统计用于 Grafana 展示 Sent KB/sec（配合 Prometheus rate）。
    if response is not None and response.request is not None and response.request.body:
        body = response.request.body
        if isinstance(body, str):
            SENT_BYTES_TOTAL.inc(len(body.encode("utf-8")))
        else:
            SENT_BYTES_TOTAL.inc(len(body))


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    if environment.web_ui is None:
        return

    @environment.web_ui.app.route("/metrics")
    def metrics():
        total = environment.stats.total
        CURRENT_RPS.set(total.current_rps or 0)
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
