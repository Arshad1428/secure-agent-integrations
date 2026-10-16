import base64
import json
import time

import pytest

GENERIC = "Invalid or expired token"


def _none_alg_token():
    def b64(data):
        raw = json.dumps(data).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    now = int(time.time())

    return (
        b64({"alg": "none", "typ": "JWT"})
        + "."
        + b64({
            "sub": "x", "role": "admin",
            "iss": "secure-agent-local", "aud": "secure-agent-api",
            "iat": now, "exp": now + 600, "jti": "a",
        })
        + "."
    )


def test_missing_token_is_rejected(client, audit_records, metric):
    before = metric("agent_auth_failures_total", reason="missing_token")

    response = client.get("/tools")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"] == "Bearer token required"
    assert (
        metric("agent_auth_failures_total", reason="missing_token")
        == before + 1
    )

    failure = [
        r for r in audit_records() if r["event"] == "auth_failure"
    ][0]

    assert failure["reason"] == "missing_token"
    assert failure["route"] == "/tools"


@pytest.mark.parametrize(
    "build, reason",
    [
        (lambda t, f: "garbage", "malformed_token"),
        (lambda t, f: _none_alg_token(), "invalid_algorithm"),
        (lambda t, f: f(secret="y" * 48), "invalid_signature"),
        (lambda t, f: f(exp=int(time.time()) - 60), "token_expired"),
        (lambda t, f: f(aud="someone-else"), "invalid_audience"),
        (lambda t, f: f(iss="someone-else"), "invalid_issuer"),
        (lambda t, f: f(role="superuser"), "invalid_role"),
        (lambda t, f: f(sub="   "), "invalid_subject"),
        (lambda t, f: f(sub="x" * 101), "invalid_subject"),
        (lambda t, f: f(drop=("jti",)), "missing_claim"),
    ],
)
def test_bad_tokens_get_generic_401_and_specific_audit(
    build, reason, client, forge, token_for,
    auth, audit_records, metric,
):
    before = metric("agent_auth_failures_total", reason=reason)

    token = build(token_for, forge)
    response = client.get("/tools", headers=auth(token))

    assert response.status_code == 401
    # The caller must learn nothing about why validation failed.
    assert response.json()["detail"] == GENERIC
    assert reason not in response.text

    assert (
        metric("agent_auth_failures_total", reason=reason)
        == before + 1
    )

    reasons = [
        r["reason"]
        for r in audit_records()
        if r["event"] == "auth_failure"
    ]

    assert reasons == [reason]


def test_tampered_signature_is_rejected(
    client, token_for, auth, audit_records,
):
    token = token_for("admin")
    head, body, sig = token.split(".")
    flipped = "A" if sig[5] != "A" else "B"
    tampered = ".".join([head, body, sig[:5] + flipped + sig[6:]])

    response = client.get("/tools", headers=auth(tampered))

    assert response.status_code == 401
    assert any(
        r.get("reason") == "invalid_signature"
        for r in audit_records()
    )


def test_valid_token_is_accepted(client, token_for, auth):
    response = client.get("/tools", headers=auth(token_for("reader")))

    assert response.status_code == 200


def test_health_needs_no_token(client):
    assert client.get("/health").status_code == 200


def test_placeholder_secret_is_refused(monkeypatch):
    from secure_agent.config import get_jwt_secret

    monkeypatch.setenv("JWT_SECRET", "replace-with-generated-secret")

    with pytest.raises(ValueError):
        get_jwt_secret()

    monkeypatch.setenv("JWT_SECRET", "short")

    with pytest.raises(ValueError):
        get_jwt_secret()
