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

        subject = claims["sub"]
        role = claims["role"]

        if (
            not isinstance(subject, str)
            or not subject.strip()
            or len(subject) > 100
        ):
            raise jwt.InvalidTokenError("Invalid subject")

        if (
            not isinstance(role, str)
            or role not in ROLE_PERMISSIONS
        ):
            raise jwt.InvalidTokenError("Invalid role")

        return claims

    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc