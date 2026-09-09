from __future__ import annotations

from fastapi.responses import JSONResponse


def error_response(
    code: str,
    message: str,
    status_code: int,
    request_id: str,
    details: list[dict] | None = None,
) -> JSONResponse:
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }
    if details is not None:
        error["details"] = details

    return JSONResponse(status_code=status_code, content={"error": error})
