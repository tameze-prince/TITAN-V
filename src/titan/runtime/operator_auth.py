from dataclasses import dataclass
from secrets import compare_digest

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from titan.config import settings


_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    subject: str
    role: str


async def require_operator(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> OperatorIdentity:
    # Development keeps the local operator surface usable without a token.
    # Production should set TITAN_OPERATOR_AUTH_REQUIRED=true and a strong token.
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

    return OperatorIdentity(
        subject=settings.operator_subject,
        role=settings.operator_role,
    )
