import json
import os
import socket

# Must be set before secure_agent is imported. Real environment
# variables take precedence over the project's .env file.
os.environ["JWT_SECRET"] = "test-only-secret-" + "x" * 40

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from prometheus_client import REGISTRY  # noqa: E402

from secure_agent.config import (  # noqa: E402
    JWT_AUDIENCE,
    JWT_ISSUER,
    get_jwt_secret,
)
from secure_agent.identity.tokens import issue_token  # noqa: E402
from secure_agent.observability import logging as audit_logging  # noqa: E402

from tests.fake_ollama import FakeOllama  # noqa: E402


@pytest.fixture(autouse=True)
def audit_file(tmp_path, monkeypatch):
    """Send audit records to a temp dir instead of the real logs/."""

    logger = audit_logging.logger

    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    monkeypatch.setattr(audit_logging, "LOG_DIR", tmp_path)

    yield tmp_path / "audit.jsonl"

    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


@pytest.fixture
def client():
    from secure_agent.api import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def audit_records(audit_file):
    def read():
        if not audit_file.exists():
            return []

        return [
            json.loads(line)
            for line in audit_file.read_text().splitlines()
            if line.strip()
        ]

    return read


@pytest.fixture
def token_for():
    def make(role="operator", subject="tester"):
        return issue_token(subject, role)

    return make


@pytest.fixture
def auth():
    def headers(token):
        return {"Authorization": f"Bearer {token}"}

    return headers


@pytest.fixture
def forge():
    """Build a signed token with arbitrary claim or key overrides."""

    import time

    def make(secret=None, algorithm="HS256", drop=(), **claims):
        now = int(time.time())

        payload = {
            "sub": "forged",
            "role": "admin",
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": now,
            "exp": now + 600,
            "jti": "forged-jti",
        }

        payload.update(claims)

        for key in drop:
            payload.pop(key, None)

        return jwt.encode(
            payload,
            secret or get_jwt_secret(),
            algorithm=algorithm,
        )

    return make


@pytest.fixture
def metric():
    """Read a Prometheus sample; absent series count as zero."""

    def read(name, **labels):
        return REGISTRY.get_sample_value(name, labels) or 0.0

    return read


@pytest.fixture
def fake_ollama(monkeypatch):
    server = FakeOllama()
    server.start()

    monkeypatch.setattr("secure_agent.agent.OLLAMA_URL", server.url)

    yield server

    server.stop()


@pytest.fixture
def dead_ollama_url():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    return f"http://127.0.0.1:{port}"
