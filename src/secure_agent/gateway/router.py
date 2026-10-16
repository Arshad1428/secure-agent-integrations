import sys
import time
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import HTTPException
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from secure_agent.authz.policies import (
    TOOL_PERMISSIONS,
    permitted_tools,
    require_permission,
)
from secure_agent.config import (
    MCP_TIMEOUT_SECONDS,
    PROJECT_ROOT,
)
from secure_agent.identity.tokens import verify_token
from secure_agent.observability.logging import audit
from secure_agent.observability.metrics import (
    TOOL_CALLS,
    TOOL_DURATION,
)


@asynccontextmanager
async def connect():
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "secure_agent.mcp.server"],
        cwd=str(PROJECT_ROOT),
    )

    try:
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(
                read,
                write,
                read_timeout_seconds=timedelta(
                    seconds=MCP_TIMEOUT_SECONDS
                ),
            ) as session:
                await session.initialize()
                yield session

    except BaseExceptionGroup as group:
        # MCP transport cleanup can wrap HTTP exceptions.
        # Preserve the original authentication/permission status.
        error = group

        while (
            isinstance(error, BaseExceptionGroup)
            and len(error.exceptions) == 1
        ):
            error = error.exceptions[0]

        if isinstance(error, HTTPException):
            raise error from None

        raise


async def list_tools(
    session: ClientSession,
    token: str,
) -> list[dict]:
    claims = verify_token(token)
    allowed = permitted_tools(claims)

    result = await session.list_tools()

    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        for tool in result.tools
        if tool.name in allowed
    ]


async def call_tool(
    session: ClientSession,
    token: str,
    name: str,
    arguments: dict,
    request_id: str,
) -> dict:
    started = time.perf_counter()
    outcome = "error"
    subject = None

    metric_name = (
        name if name in TOOL_PERMISSIONS else "unknown"
    )

    try:
        claims = verify_token(token)
        subject = claims["sub"]

        if name not in TOOL_PERMISSIONS:
            raise HTTPException(
                status_code=404,
                detail="Unknown tool",
            )

        require_permission(
            claims,
            TOOL_PERMISSIONS[name],
        )

        result = await session.call_tool(
            name,
            arguments=arguments,
        )

        outcome = (
            "error" if result.isError else "success"
        )

        return result.model_dump(
            mode="json",
            exclude_none=True,
        )

    except HTTPException:
        outcome = "denied"
        raise

    finally:
        elapsed = time.perf_counter() - started

        TOOL_CALLS.labels(
            tool=metric_name,
            outcome=outcome,
        ).inc()

        TOOL_DURATION.labels(
            tool=metric_name,
        ).observe(elapsed)

        audit(
            "tool_call",
            request_id,
            subject=subject,
            tool=metric_name,
            outcome=outcome,
            duration_ms=round(elapsed * 1000, 2),
        )