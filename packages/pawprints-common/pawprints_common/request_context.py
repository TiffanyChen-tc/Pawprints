from __future__ import annotations

from contextvars import ContextVar

from fastapi import Request


REQUEST_ID_HEADER = "X-Request-Id"
_current_request_id: ContextVar[str] = ContextVar("pawprints_request_id", default="")


def current_request_id() -> str:
    return _current_request_id.get()


def request_id_for(request: Request) -> str:
    return current_request_id() or request.headers.get(REQUEST_ID_HEADER, "")


def set_current_request_id(request_id: str):
    return _current_request_id.set(request_id)


def reset_current_request_id(token) -> None:
    _current_request_id.reset(token)
