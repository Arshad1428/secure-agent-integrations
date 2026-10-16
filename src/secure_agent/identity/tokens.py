import secrets
import time

import jwt
from fastapi import HTTPException

from secure_agent.authz.policies import ROLE_PERMISSIONS
from secure_agent.config import (
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_EXPIRY_MINUTES,
    JWT_ISSUER,
    get_jwt_secret,
)


class AuthError(HTTPException):
    """401 with a machine-readable reason for audit logs and metrics.

    The HTTP response stays generic so callers learn nothing about
    why validation failed. The reason is bounded to the fixed set
    returned by _reason_for, so it is safe as a metric label.
    """

    def __init__(self, reason: str):
        detail = (
            "Bearer token required"
            if reason == "missing_token"
            else "Invalid or expired token"
        )

        super().__init__(
            status_code=401,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

        self.reason = reason


def _reason_for(exc: jwt.InvalidTokenError) -> str:
    if isinstance(exc, jwt.ExpiredSignatureError):
        return "token_expired"

    if isinstance(exc, jwt.InvalidSignatureError):
        return "invalid_signature"

    if isinstance(exc, jwt.InvalidAudienceError):
        return "invalid_audience"

    if isinstance(exc, jwt.InvalidIssuerError):
        return "invalid_issuer"

    if isinstance(exc, jwt.InvalidAlgorithmError):
        return "invalid_algorithm"

    if isinstance(exc, jwt.MissingRequiredClaimError):
        return "missing_claim"

    if isinstance(exc, jwt.DecodeError):
        return "malformed_token"

    return "invalid_token"


def issue_token(
    subject: str = "demo-user",
    role: str = "operator",
) -> str:
    subject = subject.strip()

    if not subject or len(subject) > 100:
        raise ValueError(
            "Subject must contain between 1 and 100 characters"
        )

    if role not in ROLE_PERMISSIONS:
        raise ValueError("Unknown role")

    now = int(time.time())

    payload = {
        "sub": subject,
        "role": role,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + JWT_EXPIRY_MINUTES * 60,
        "jti": secrets.token_hex(16),
    }

    return jwt.encode(
        payload,
        get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def verify_token(token: str) -> dict:
    try:
        claims = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={
                "require": [
                    "sub",
                    "role",
                    "iss",
                    "aud",
                    "iat",
                    "exp",
                    "jti",
                ]
            },
        )

    except jwt.InvalidTokenError as exc:
        raise AuthError(_reason_for(exc)) from exc

    subject = claims["sub"]
    role = claims["role"]

    if (
        not isinstance(subject, str)
        or not subject.strip()
        or len(subject) > 100
    ):
        raise AuthError("invalid_subject")

    if not isinstance(role, str) or role not in ROLE_PERMISSIONS:
        raise AuthError("invalid_role")

    return claims
