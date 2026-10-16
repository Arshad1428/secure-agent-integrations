import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

LOG_DIR = PROJECT_ROOT / "logs"

JWT_ISSUER = "secure-agent-local"
JWT_AUDIENCE = "secure-agent-api"
JWT_ALGORITHM = "HS256"

JWT_EXPIRY_MINUTES = int(
    os.getenv("JWT_EXPIRY_MINUTES", "30")
)

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434",
).rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:7b-instruct",
)

MAX_AGENT_STEPS = int(
    os.getenv("MAX_AGENT_STEPS", "8")
)

OLLAMA_TIMEOUT_SECONDS = float(
    os.getenv("OLLAMA_TIMEOUT_SECONDS", "180")
)

MCP_TIMEOUT_SECONDS = float(
    os.getenv("MCP_TIMEOUT_SECONDS", "20")
)

if not 1 <= JWT_EXPIRY_MINUTES <= 1440:
    raise ValueError(
        "JWT_EXPIRY_MINUTES must be between 1 and 1440"
    )

if not 1 <= MAX_AGENT_STEPS <= 20:
    raise ValueError(
        "MAX_AGENT_STEPS must be between 1 and 20"
    )

if OLLAMA_TIMEOUT_SECONDS <= 0 or MCP_TIMEOUT_SECONDS <= 0:
    raise ValueError("Timeout values must be positive")


def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")

    if len(secret) < 32 or secret.startswith("replace-"):
        raise ValueError(
            "JWT_SECRET is missing or invalid. "
            "Run: python scripts/local_identity.py init"
        )

    return secret