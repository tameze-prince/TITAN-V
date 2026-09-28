from dataclasses import dataclass
from secrets import compare_digest

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from titan.config import settings


_bearer = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": frozenset({"control_plane:read"}),
    "operator": frozenset(
        {
            "control_plane:read",
            "recovery:approve",
            "recovery:rollback",
            "task:approve",
        }
    ),
    "admin": frozenset(
        {
            "control_plane:read",
            "recovery:approve",
            "recovery:rollback",
            "task:approve",
            "policy:admin",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    subject: str
    role: str

    def has_permission(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, frozenset())

    def require_permission(self, permission: str) -> None:
        if self.has_permission(permission):
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operator role '{self.role}' lacks permission '{permission}'",
        )


async def require_operator(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> OperatorIdentity:
    if not settings.operator_auth_required and settings.environment == "development":
        return OperatorIdentity(
            subject=settings.operator_subject,
            role=settings.operator_role,
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operator authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    configured = settings.operator_api_token
    if not configured or not compare_digest(credentials.credentials, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid operator credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    identity = OperatorIdentity(
        subject=settings.operator_subject,
        role=settings.operator_role,
    )

    if identity.role not in ROLE_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unsupported operator role '{identity.role}'",
        )

    return identity
