FROM python:3.12-slim AS base

WORKDIR /repo

COPY packages/pawprints-common packages/pawprints-common
COPY services/auth services/auth

RUN python -m pip install --no-cache-dir -e packages/pawprints-common -e services/auth

FROM base AS test

RUN python -m pip install --no-cache-dir -e "services/auth[dev]"

FROM base AS runtime

WORKDIR /repo/services/auth
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
