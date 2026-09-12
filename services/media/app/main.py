from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from pawprints_common.errors import error_response
from pawprints_common.observability import install_request_context_and_metrics
from pawprints_common.request_context import request_id_for

from app.db import engine
from app.internal import router as internal_router
from app.routes import router as media_router


app = FastAPI(title="Pawprints Media Service")
install_request_context_and_metrics(app, "media")
app.include_router(media_router)
app.include_router(internal_router)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    return error_response("validation_failed", "Some fields are invalid.", 422, request_id_for(request))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return {"status": "ready"}
