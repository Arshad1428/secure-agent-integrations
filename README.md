# Secure Agent Integrations

A local AI agent with authenticated MCP tools, gateway routing,
JWT identities, audit logs, and metrics.

## Technology

- Python 3.12
- FastAPI
- Ollama
- MCP Python SDK v1
- PyJWT
- Prometheus client

## Setup — Windows Git Bash

Run from the project root:

```bash
python -m venv .venv
source .venv/Scripts/activate

python -m pip install -r requirements.txt
python -m pip install -e .

python scripts/local_identity.py init
```

The first installation command installs external dependencies.
The second registers the local secure_agent package in editable mode.

The initialization command creates .env with a generated JWT secret.
It does not overwrite an existing .env.

Select .venv/Scripts/python.exe as the interpreter in VS Code.

## Ollama

Make sure Ollama is installed and running.

Download the configured model if needed:

```bash
ollama pull qwen2.5:7b-instruct
```

If Ollama is not already running, start it in a separate terminal:

```bash
ollama serve
```

## Start the application

```bash
python -m secure_agent
```

Open http://127.0.0.1:8000/docs.

## Generate a token

Open another Git Bash terminal in the project root:

```bash
source .venv/Scripts/activate
python scripts/local_identity.py token
```

Copy the token.

In the API documentation, click Authorize and paste only the token.
Do not add the word Bearer.

Tokens expire after 30 minutes by default.

## Ask the agent

Use POST /agent with:

```json
{
  "prompt": "Find the price of product P100 and calculate the total for 3 units."
}
```

The demo product costs INR 65,000.
The total for three units is INR 195,000.

Responses contain:

- answer
- tools_used
- request_id

The local model determines which tools it calls.

## Project organization

- config.py: environment settings and paths
- __main__.py: application entry point
- api.py: HTTP endpoints and request monitoring
- agent.py: Ollama conversation and tool-calling loop
- identity/tokens.py: JWT issuance and validation
- authz/policies.py: role and tool permissions
- gateway/router.py: MCP connection and authorized routing
- mcp/server.py: MCP server registration
- mcp/tools/: calculator and demo product tools
- observability/logging.py: rotating JSON audit logs
- observability/metrics.py: request and tool metrics
- scripts/local_identity.py: configuration and token CLI
- tests/: offline test suite with a fake Ollama server

## Request flow

1. FastAPI validates the JWT.
2. The gateway discovers tools from a private MCP subprocess.
3. Permitted tool schemas are passed to Ollama.
4. Ollama requests a tool call.
5. The gateway revalidates identity and checks permission.
6. The MCP server executes the tool.
7. The result returns to Ollama for the final answer.
8. Logs and metrics record execution metadata.

The MCP subprocess uses the same Python interpreter as the API.
It communicates over stdio and has no network listener.

## Roles

| Role | Product lookup | Calculator | Metrics |
|---|---|---|---|
| reader | Yes | No | No |
| operator | Yes | Yes | No |
| admin | Yes | Yes | Yes |

Examples:

```bash
python scripts/local_identity.py token --subject arshad --role reader
python scripts/local_identity.py token --subject arshad --role admin
```

Token issuance is a trusted local operator command.
Anyone with access to the signing secret can issue tokens.

## Endpoints

| Endpoint | Purpose |
|---|---|
| GET /health | API liveness |
| GET /docs | Interactive API documentation |
| POST /agent | Ask the agent |
| GET /tools | List permitted tool schemas |
| POST /tools/{name} | Execute a tool through the gateway |
| GET /metrics | View metrics using an admin token |

Example body for POST /tools/calculate:

```json
{
  "arguments": {
    "operation": "multiply",
    "a": 12,
    "b": 12
  }
}
```

MCP tool validation or execution errors appear as isError in the
tool response. HTTP 200 alone does not mean the tool succeeded.

## Logs and metrics

Audit events are written to logs/audit.jsonl.

Event types:

| Event | Written when | Notable fields |
|---|---|---|
| http_request | every request | route, status, duration_ms, subject, role, reason, cause |
| auth_failure | a token is missing or rejected | reason, route, client |
| tool_call | the gateway handles a tool call | subject, tool, outcome, reason, duration_ms |
| request_error | an unhandled exception occurs | error_type |

subject and role are null when the request was not authenticated.
reason explains a failed request. For 401 it is one of: missing_token,
malformed_token, invalid_signature, invalid_algorithm, token_expired,
invalid_audience, invalid_issuer, missing_claim, invalid_subject,
invalid_role. For 403 it is missing_permission:<permission>. For
other failures it is the error message returned to the caller.
cause is the exception type behind a failure, such as ConnectError
or ReadTimeout when Ollama is unreachable or slow.

HTTP responses stay generic for authentication failures. The
specific reason is only written to the audit log and metrics.

Tokens, prompts, tool arguments, and tool result contents are
excluded from audit records.

Logs rotate at 2 MB with three backups.

The /metrics endpoint exposes HTTP and tool counts and duration.
agent_auth_failures_total counts rejected tokens by reason.
Metrics reset when the application restarts. Run one API worker.

## Configuration

Settings load from the project root .env.

| Setting | Purpose |
|---|---|
| JWT_SECRET | Signing secret |
| JWT_EXPIRY_MINUTES | Token lifetime |
| OLLAMA_URL | Ollama address |
| OLLAMA_MODEL | Installed tool-capable model |
| MAX_AGENT_STEPS | Maximum model rounds |
| OLLAMA_TIMEOUT_SECONDS | Ollama HTTP client timeout |
| MCP_TIMEOUT_SECONDS | MCP request timeout |

Timeouts apply to backend requests, not to the entire agent operation.

## Troubleshooting

- 401: token missing, invalid, or expired. The audit log
  auth_failure event gives the exact reason.
- 403: the current role lacks permission. The reason field names
  the missing permission.
- 502: check Ollama and model installation. The reason and cause
  fields of the http_request event show what failed.
- 504: Ollama exceeded its configured timeout.
- ModuleNotFoundError: activate .venv and run
  python -m pip install -e .
- Existing .env: initialization preserves it; edit it manually.

## Tests

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

The suite needs no Ollama installation. It starts a fake Ollama
server to exercise the agent loop, covers authentication failures,
role permissions, gateway enforcement, error mapping, audit
content, and metrics, and writes audit records to a temporary
directory. It tests the plumbing, not the quality of a real model.

## Scope

The project runs locally using Ollama and locally issued JWT tokens.

Product records are fixed demo data.
No AWS services, database, OIDC provider, Docker deployment,
or distributed tracing is configured.