from tests.fake_ollama import answer, tool_call

PROMPT = {"prompt": "Find P100 and total for 3 units"}


def two_step(messages, tools):
    """get_product, then calculate if offered, then finish."""

    used = [m for m in messages if m["role"] == "tool"]

    if not used:
        return tool_call("get_product", {"product_id": "P100"})

    if len(used) == 1 and "calculate" in tools:
        return tool_call(
            "calculate",
            {"operation": "multiply", "a": 65000, "b": 3},
        )

    return answer("done")


def test_operator_flow_uses_both_tools(
    client, fake_ollama, token_for, auth,
):
    fake_ollama.behavior = two_step

    response = client.post(
        "/agent", json=PROMPT, headers=auth(token_for("operator"))
    )

    assert response.status_code == 200

    body = response.json()

    assert body["tools_used"] == ["get_product", "calculate"]
    assert body["answer"] == "done"
    assert body["request_id"] == response.headers["x-request-id"]

    assert all(
        sorted(offered) == ["calculate", "get_product"]
        for offered in fake_ollama.seen
    )


def test_reader_is_only_offered_permitted_tools(
    client, fake_ollama, token_for, auth,
):
    fake_ollama.behavior = two_step

    response = client.post(
        "/agent", json=PROMPT, headers=auth(token_for("reader"))
    )

    assert response.status_code == 200
    assert response.json()["tools_used"] == ["get_product"]
    assert all(offered == ["get_product"] for offered in fake_ollama.seen)


def test_gateway_blocks_a_model_that_ignores_its_tool_list(
    client, fake_ollama, token_for, auth, audit_records,
):
    # Simulates a prompt-injected or misbehaving model.
    fake_ollama.behavior = lambda m, t: tool_call(
        "calculate", {"operation": "add", "a": 1, "b": 1}
    )

    response = client.post(
        "/agent",
        json=PROMPT,
        headers=auth(token_for("reader", "alice")),
    )

    assert response.status_code == 403

    records = audit_records()

    denied = [
        r for r in records
        if r["event"] == "tool_call" and r["outcome"] == "denied"
    ]

    assert denied[0]["subject"] == "alice"

    request = [r for r in records if r["event"] == "http_request"][0]

    assert request["status"] == 403
    assert request["reason"] == "missing_permission:tools:calculate"


def test_runaway_tool_loop_stops_at_step_limit(
    client, fake_ollama, token_for, auth, audit_records, monkeypatch,
):
    monkeypatch.setattr("secure_agent.agent.MAX_AGENT_STEPS", 3)

    fake_ollama.behavior = lambda m, t: tool_call(
        "get_product", {"product_id": "P100"}
    )

    response = client.post(
        "/agent", json=PROMPT, headers=auth(token_for("operator"))
    )

    assert response.status_code == 502
    assert len(fake_ollama.seen) == 3

    request = audit_records()[-1]

    assert request["event"] == "http_request"
    assert "step limit" in request["reason"]


def test_malformed_tool_arguments_are_rejected(
    client, fake_ollama, token_for, auth,
):
    fake_ollama.behavior = lambda m, t: tool_call(
        "get_product", "{not json"
    )

    response = client.post(
        "/agent", json=PROMPT, headers=auth(token_for("operator"))
    )

    assert response.status_code == 502
    assert "invalid tool arguments" in response.json()["detail"]


def test_unreachable_ollama_is_502_and_cause_is_audited(
    client, dead_ollama_url, monkeypatch,
    token_for, auth, audit_records,
):
    monkeypatch.setattr(
        "secure_agent.agent.OLLAMA_URL", dead_ollama_url
    )

    response = client.post(
        "/agent", json=PROMPT, headers=auth(token_for("operator"))
    )

    assert response.status_code == 502

    request = audit_records()[-1]

    assert request["status"] == 502
    assert "Ollama request failed" in request["reason"]
    assert request["cause"] == "ConnectError"
    assert request["subject"] == "tester"


def test_slow_ollama_is_504_and_cause_is_audited(
    client, fake_ollama, monkeypatch, token_for, auth, audit_records,
):
    monkeypatch.setattr(
        "secure_agent.agent.OLLAMA_TIMEOUT_SECONDS", 0.2
    )

    fake_ollama.delay = 1.0

    response = client.post(
        "/agent", json=PROMPT, headers=auth(token_for("operator"))
    )

    assert response.status_code == 504

    request = audit_records()[-1]

    assert request["status"] == 504
    assert request["cause"] == "ReadTimeout"


def test_blank_and_unknown_fields_are_rejected(
    client, token_for, auth,
):
    headers = auth(token_for("operator"))

    assert client.post(
        "/agent", json={"prompt": "   "}, headers=headers
    ).status_code == 422

    assert client.post(
        "/agent", json={"prompt": "hi", "x": 1}, headers=headers
    ).status_code == 422

    assert client.post(
        "/agent", json={"prompt": "x" * 8001}, headers=headers
    ).status_code == 422


def test_agent_requires_authentication(client):
    assert client.post("/agent", json=PROMPT).status_code == 401
