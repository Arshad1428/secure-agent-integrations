from tests.fake_ollama import answer, tool_call


def http_events(records):
    return [r for r in records if r["event"] == "http_request"]


def test_authenticated_requests_record_identity(
    client, token_for, auth, audit_records,
):
    response = client.get(
        "/tools", headers=auth(token_for("operator", "bob"))
    )

    event = http_events(audit_records())[0]

    assert event["subject"] == "bob"
    assert event["role"] == "operator"
    assert event["status"] == 200
    assert event["route"] == "/tools"
    assert event["request_id"] == response.headers["x-request-id"]
    assert event["reason"] is None


def test_authorization_failure_records_who_and_why(
    client, token_for, auth, audit_records,
):
    client.get("/metrics", headers=auth(token_for("reader", "alice")))

    event = http_events(audit_records())[0]

    assert event["status"] == 403
    assert event["subject"] == "alice"
    assert event["role"] == "reader"
    assert event["reason"] == "missing_permission:monitor:read"


def test_unauthenticated_failure_has_no_identity_but_has_reason(
    client, audit_records,
):
    client.get("/tools")

    event = http_events(audit_records())[0]

    assert event["status"] == 401
    assert event["subject"] is None
    assert event["reason"] == "missing_token"


def test_audit_log_excludes_secrets_and_content(
    client, fake_ollama, token_for, auth, audit_file, audit_records,
):
    marker = "SENSITIVE-PROMPT-MARKER-12345"

    def behavior(messages, tools):
        if not any(m["role"] == "tool" for m in messages):
            return tool_call("get_product", {"product_id": "P100"})

        return answer("done")

    fake_ollama.behavior = behavior

    token = token_for("operator")

    client.post(
        "/agent",
        json={"prompt": marker},
        headers=auth(token),
    )

    raw = audit_file.read_text()

    from secure_agent.config import get_jwt_secret

    assert raw
    assert marker not in raw
    assert token not in raw
    assert get_jwt_secret() not in raw
    # Tool arguments and results are not logged either.
    assert "P100" not in raw
    assert "Laptop" not in raw
    assert "65000" not in raw


def test_metrics_cover_http_and_tools(
    client, token_for, auth, metric,
):
    http_before = metric(
        "agent_http_requests_total",
        method="POST", route="/tools/{name}", status="200",
    )
    tool_before = metric(
        "agent_tool_calls_total",
        tool="get_product", outcome="success",
    )

    client.post(
        "/tools/get_product",
        json={"arguments": {"product_id": "P100"}},
        headers=auth(token_for("reader")),
    )

    assert metric(
        "agent_http_requests_total",
        method="POST", route="/tools/{name}", status="200",
    ) == http_before + 1

    assert metric(
        "agent_tool_calls_total",
        tool="get_product", outcome="success",
    ) == tool_before + 1


def test_unknown_paths_do_not_create_unbounded_labels(
    client, metric,
):
    before = metric(
        "agent_http_requests_total",
        method="GET", route="unmatched", status="404",
    )

    for path in ("/a", "/b/c", "/d?x=1"):
        client.get(path)

    assert metric(
        "agent_http_requests_total",
        method="GET", route="unmatched", status="404",
    ) == before + 3


def test_log_records_are_valid_json_with_timestamps(
    client, audit_records,
):
    client.get("/health")

    for record in audit_records():
        assert {"timestamp", "event", "request_id"} <= record.keys()
