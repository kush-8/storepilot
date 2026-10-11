# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/home/storepilot

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 storepilot
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_CACHE_DIR=/root/.cache/uv uv sync --locked --no-dev --no-install-project

COPY app ./app
COPY knowledge_base ./knowledge_base
COPY database/retail.db ./database/retail.db
COPY openapi.json ./openapi.json
COPY docker/entrypoint.py ./docker/entrypoint.py
RUN mkdir -p /app/state /app/cache \
    && chown -R storepilot:storepilot /app/state /app/cache

USER storepilot
EXPOSE 8000
ENTRYPOINT ["python", "docker/entrypoint.py"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
