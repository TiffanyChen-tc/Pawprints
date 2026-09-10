from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from pawprints_common.errors import error_response

from app.categories import router as categories_router
from app.events import router as events_router
from app.internal import router as internal_router


app = FastAPI(title="Pawprints Event Service")
app.include_router(categories_router)
app.include_router(events_router)
app.include_router(internal_router)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    return error_response("validation_failed", "Some fields are invalid.", 422, request.headers.get("X-Request-Id", ""))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
