import pytest

PRODUCT = {"arguments": {"product_id": "p100"}}
MULTIPLY = {
    "arguments": {"operation": "multiply", "a": 65000, "b": 3}
}


def names(response):
    return sorted(t["function"]["name"] for t in response.json())


@pytest.mark.parametrize(
    "role, expected",
    [
        ("reader", ["get_product"]),
        ("operator", ["calculate", "get_product"]),
        ("admin", ["calculate", "get_product"]),
    ],
)
def test_discovery_is_filtered_by_role(
    role, expected, client, token_for, auth,
):
    response = client.get("/tools", headers=auth(token_for(role)))

    assert response.status_code == 200
    assert names(response) == expected


@pytest.mark.parametrize(
    "role, status",
    [("reader", 403), ("operator", 200), ("admin", 200)],
)
def test_calculate_requires_calculate_permission(
    role, status, client, token_for, auth,
):
    response = client.post(
        "/tools/calculate",
        json=MULTIPLY,
        headers=auth(token_for(role)),
    )

    assert response.status_code == status

    if status == 200:
        assert response.json()["isError"] is False
        assert "195000" in response.json()["content"][0]["text"]


@pytest.mark.parametrize("role", ["reader", "operator", "admin"])
def test_every_role_can_read_products(
    role, client, token_for, auth,
):
    response = client.post(
        "/tools/get_product",
        json=PRODUCT,
        headers=auth(token_for(role)),
    )

    assert response.status_code == 200
    assert response.json()["isError"] is False
    assert "Laptop" in response.json()["content"][0]["text"]


def test_denied_tool_call_is_audited_with_reason(
    client, token_for, auth, audit_records, metric,
):
    before = metric(
        "agent_tool_calls_total", tool="calculate", outcome="denied"
    )

    client.post(
        "/tools/calculate",
        json=MULTIPLY,
        headers=auth(token_for("reader", "alice")),
    )

    denied = [
        r for r in audit_records()
        if r["event"] == "tool_call" and r["outcome"] == "denied"
    ]

    assert len(denied) == 1
    assert denied[0]["subject"] == "alice"
    assert denied[0]["tool"] == "calculate"
    assert denied[0]["reason"] == "missing_permission:tools:calculate"

    assert (
        metric(
            "agent_tool_calls_total",
            tool="calculate", outcome="denied",
        )
        == before + 1
    )


def test_unknown_tool_is_404_and_not_a_metric_label(
    client, token_for, auth, metric,
):
    response = client.post(
        "/tools/rm_rf_everything",
        json={"arguments": {}},
        headers=auth(token_for("admin")),
    )

    assert response.status_code == 404
    # Unknown names are folded into one bounded label value.
    assert metric(
        "agent_tool_calls_total",
        tool="rm_rf_everything", outcome="denied",
    ) == 0


@pytest.mark.parametrize(
    "arguments, fragment",
    [
        ({"operation": "divide", "a": 1, "b": 0}, "divide by zero"),
        ({"operation": "pow", "a": 1, "b": 2}, "validation error"),
        ({"operation": "add", "a": 1}, "validation error"),
        (
            {"operation": "multiply", "a": 1e308, "b": 1e308},
            "numeric limits",
        ),
    ],
)
def test_tool_errors_surface_as_is_error(
    arguments, fragment, client, token_for, auth,
):
    response = client.post(
        "/tools/calculate",
        json={"arguments": arguments},
        headers=auth(token_for("operator")),
    )

    # HTTP 200 does not mean success; isError carries the outcome.
    assert response.status_code == 200
    assert response.json()["isError"] is True
    assert fragment in response.json()["content"][0]["text"]


def test_unknown_product_is_a_tool_error(client, token_for, auth):
    response = client.post(
        "/tools/get_product",
        json={"arguments": {"product_id": "ZZZ"}},
        headers=auth(token_for("reader")),
    )

    assert response.json()["isError"] is True


def test_request_bodies_reject_unknown_fields(
    client, token_for, auth,
):
    response = client.post(
        "/tools/calculate",
        json={"arguments": {}, "extra": 1},
        headers=auth(token_for("operator")),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "role, status",
    [("reader", 403), ("operator", 403), ("admin", 200)],
)
def test_metrics_endpoint_is_admin_only(
    role, status, client, token_for, auth,
):
    response = client.get("/metrics", headers=auth(token_for(role)))

    assert response.status_code == status


def test_metrics_requires_authentication(client):
    assert client.get("/metrics").status_code == 401
