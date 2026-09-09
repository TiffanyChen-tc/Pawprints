from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt


JWT_ISSUER = "pawprints-auth"
JWT_AUDIENCE = "pawprints-api"


class JWTValidationError(Exception):
    """Raised when an access token cannot be trusted."""


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID


def verify_access_token(
    token: str,
    public_key_pem: str,
    issuer: str,
    audience: str,
) -> AuthenticatedUser:
    if issuer != JWT_ISSUER or audience != JWT_AUDIENCE:
        raise JWTValidationError("unsupported JWT issuer or audience")

    try:
        payload = jwt.decode(
            token,
            public_key_pem,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options={"require": ["sub", "iss", "aud", "exp"]},
        )
        return AuthenticatedUser(user_id=UUID(str(payload["sub"])))
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise JWTValidationError("invalid access token") from exc
