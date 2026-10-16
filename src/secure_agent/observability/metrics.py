from prometheus_client import Counter, Histogram


HTTP_REQUESTS = Counter(
    "agent_http_requests_total",
    "Number of HTTP requests",
    ["method", "route", "status"],
)

HTTP_DURATION = Histogram(
    "agent_http_duration_seconds",
    "HTTP request duration",
    ["route"],
)

TOOL_CALLS = Counter(
    "agent_tool_calls_total",
    "Number of tool calls",
    ["tool", "outcome"],
)

TOOL_DURATION = Histogram(
    "agent_tool_duration_seconds",
    "Tool execution duration",
    ["tool"],
)

AUTH_FAILURES = Counter(
    "agent_auth_failures_total",
    "Number of rejected authentication attempts",
    ["reason"],
)
