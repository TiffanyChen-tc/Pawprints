from __future__ import annotations

from dataclasses import dataclass
import hmac
from collections.abc import Mapping, Set


class InternalAuthError(Exception):
    """Raised when an internal service request is not authorized."""


@dataclass(frozen=True)
class InternalCaller:
    service_name: str


def verify_internal_request(
    caller: str,
    token: str,
    allowed_callers: Set[str],
    expected_tokens: Mapping[str, str],
) -> InternalCaller:
    if caller not in allowed_callers:
        raise InternalAuthError("internal caller is not allowed for this endpoint")

    expected_token = expected_tokens.get(caller)
    if expected_token is None:
        raise InternalAuthError("unknown internal caller")

    if not hmac.compare_digest(token, expected_token):
        raise InternalAuthError("invalid internal token")

    return InternalCaller(service_name=caller)
