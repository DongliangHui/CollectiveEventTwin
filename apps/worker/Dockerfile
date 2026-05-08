FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/api/pyproject.toml /app/apps/api/pyproject.toml
COPY apps/api/alembic.ini /app/apps/api/alembic.ini
COPY apps/api/alembic /app/apps/api/alembic
COPY apps/api/src /app/apps/api/src
COPY apps/worker/pyproject.toml /app/apps/worker/pyproject.toml
COPY apps/worker/src /app/apps/worker/src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e /app/apps/api \
    && python -m pip install --no-cache-dir -e /app/apps/worker

CMD ["python", "-m", "worldline_worker.main"]
