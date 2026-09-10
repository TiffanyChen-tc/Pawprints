FROM python:3.12-slim

WORKDIR /repo

COPY packages/pawprints-common ./packages/pawprints-common
COPY services/event ./services/event

RUN pip install --no-cache-dir -e ./packages/pawprints-common -e ./services/event

WORKDIR /repo/services/event

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
