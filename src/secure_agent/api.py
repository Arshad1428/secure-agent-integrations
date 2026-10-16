import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
)
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)
from starlette.exceptions import (
    HTTPException as StarletteHTTPException,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from secure_agent.agent import run_agent
from secure_agent.authz.policies import require_permission
from secure_agent.config import get_jwt_secret
from secure_agent.gateway.router import (
    call_tool,
    connect,
    list_tools,
)
from secure_agent.identity.tokens import AuthError, verify_token
from secure_agent.observability.logging import (
    audit,
    configure_logging,
)
from secure_agent.observability.metrics import (
    AUTH_FAILURES,
    HTTP_DURATION,
    HTTP_REQUESTS,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_jwt_secret()
    configure_logging()
    yield


app = FastAPI(
    title="Secure Local AI Agent",
    version="0.1.0",
    lifespan=lifespan,
)

bearer = HTTPBearer(auto_error=False)


def authenticated(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer),
    ],
) -> str:
    if credentials is None:
        raise AuthError("missing_token")

    claims = verify_token(credentials.credentials)

    # Shared with the audit middleware through the ASGI scope.
    request.state.subject = claims["sub"]
    request.state.role = claims["role"]

    return credentials.credentials


Token = Annotated[str, Depends(authenticated)]


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(
        min_length=1,
        max_length=8000,
    )

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Prompt cannot be blank")

        return value


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arguments: dict[str, Any] = Field(
        default_factory=dict
    )


@app.middleware("http")
async def observe_request(request: Request, call_next):
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id

    started = time.perf_counter()

    try:
        response = await call_next(request)

    except Exception as exc:
        request.state.error_reason = "unhandled_exception"
        request.state.error_cause = type(exc).__name__

        audit(
            "request_error",
            request_id,
            error_type=type(exc).__name__,
        )

        response = JSONResponse(
            status_code=502,
            content={
                "detail": (
                    "Backend failure. Check the audit log."
                ),
                "request_id": request_id,
            },
        )

    elapsed = time.perf_counter() - started

    route = getattr(
        request.scope.get("route"),
        "path",
        "unmatched",
    )

    HTTP_REQUESTS.labels(
        method=request.method,
        route=route,
        status=str(response.status_code),
    ).inc()

    HTTP_DURATION.labels(
        route=route,
    ).observe(elapsed)

    audit(
        "http_request",
        request_id,
        method=request.method,
        route=route,
        status=response.status_code,
        duration_ms=round(elapsed * 1000, 2),
        subject=getattr(request.state, "subject", None),
        role=getattr(request.state, "role", None),
        reason=getattr(request.state, "error_reason", None),
        cause=getattr(request.state, "error_cause", None),
    )

    response.headers["X-Request-ID"] = request_id

    return response


@app.exception_handler(StarletteHTTPException)
async def record_http_error(
    request: Request,
    exc: StarletteHTTPException,
):
    """Record why a request failed, then return the normal response.

    Only the machine-readable reason, the HTTP status text, and the
    exception type of the underlying cause are stored. Tokens,
    prompts, and arguments are never read here.
    """

    reason = getattr(exc, "reason", None) or str(exc.detail)

    request.state.error_reason = reason

    if exc.__cause__ is not None:
        request.state.error_cause = type(exc.__cause__).__name__

    if isinstance(exc, AuthError):
        AUTH_FAILURES.labels(reason=exc.reason).inc()

        audit(
            "auth_failure",
            getattr(request.state, "request_id", "unknown"),
            reason=exc.reason,
            method=request.method,
            route=getattr(
                request.scope.get("route"),
                "path",
                "unmatched",
            ),
            client=(
                request.client.host if request.client else None
            ),
        )

    return await http_exception_handler(request, exc)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": "local",
        "note": "API liveness only",
    }


@app.post("/agent")
async def invoke_agent(
    body: AgentRequest,
    request: Request,
    token: Token,
):
    return await run_agent(
        prompt=body.prompt,
        token=token,
        request_id=request.state.request_id,
    )


@app.get("/tools")
async def available_tools(token: Token):
    async with connect() as session:
        return await list_tools(session, token)


@app.post("/tools/{name}")
async def execute_tool(
    name: str,
    body: ToolRequest,
    request: Request,
    token: Token,
):
    async with connect() as session:
        return await call_tool(
            session=session,
            token=token,
            name=name,
            arguments=body.arguments,
            request_id=request.state.request_id,
        )


@app.get("/metrics")
def metrics(token: Token):
    claims = verify_token(token)
    require_permission(claims, "monitor:read")

    return Response(
        content=generate_latest(),
        headers={
            "Content-Type": CONTENT_TYPE_LATEST,
        },
    )