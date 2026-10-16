from fastapi import HTTPException


class PermissionDenied(HTTPException):
    """403 carrying the missing permission for audit logs."""

    def __init__(self, permission: str):
        super().__init__(
            status_code=403,
            detail=(
                "This identity does not have "
                "the required permission"
            ),
        )

        self.reason = f"missing_permission:{permission}"


ROLE_PERMISSIONS = {
    "reader": frozenset({
        "tools:read",
    }),
    "operator": frozenset({
        "tools:read",
        "tools:calculate",
    }),
    "admin": frozenset({
        "tools:read",
        "tools:calculate",
        "monitor:read",
    }),
}

TOOL_PERMISSIONS = {
    "get_product": "tools:read",
    "calculate": "tools:calculate",
}


def require_permission(
    claims: dict,
    permission: str,
) -> None:
    permissions = ROLE_PERMISSIONS.get(
        claims.get("role"),
        frozenset(),
    )

    if permission not in permissions:
        raise PermissionDenied(permission)


def permitted_tools(claims: dict) -> set[str]:
    permissions = ROLE_PERMISSIONS.get(
        claims.get("role"),
        frozenset(),
    )

    return {
        name
        for name, permission in TOOL_PERMISSIONS.items()
        if permission in permissions
    }