from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["path", "status"]
)

WEBHOOK_REQUESTS_TOTAL = Counter(
    "webhook_requests_total",
    "Total number of webhook processing outcomes",
    ["result"]
)

REQUEST_LATENCY_MS = Histogram(
    "request_latency_ms",
    "Request latency in milliseconds",
    buckets=(10, 50, 100, 200, 500, 1000, float("inf"))
)
