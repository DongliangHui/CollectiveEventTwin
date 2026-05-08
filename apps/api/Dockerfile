FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/api/pyproject.toml /app/apps/api/pyproject.toml
COPY apps/api/alembic.ini /app/apps/api/alembic.ini
COPY apps/api/alembic /app/apps/api/alembic
COPY apps/api/src /app/apps/api/src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e /app/apps/api

WORKDIR /app/apps/api

CMD ["sh", "-c", "alembic upgrade head && python -m worldline_api.seed && uvicorn worldline_api.main:app --host 0.0.0.0 --port 8080"]
