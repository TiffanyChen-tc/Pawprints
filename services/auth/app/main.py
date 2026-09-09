from __future__ import annotations

from fastapi import FastAPI

from app.routes import router


app = FastAPI(title="Pawprints Auth")
app.include_router(router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
