# syntax=docker/dockerfile:1.6

FROM python:3.14-slim AS builder
WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && pip install --no-cache-dir -U pip uv \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN uv pip compile pyproject.toml -o requirements.txt && \
    python -m pip wheel --no-cache-dir -r requirements.txt -w /wheels && \
    rm -f requirements.txt

FROM python:3.14-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY app ./app
COPY bot ./bot
