FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_HOST=0.0.0.0 APP_PORT=8000

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgomp1 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY . .
EXPOSE ${APP_PORT}
CMD ["sh", "-c", "uv run uvicorn app.main:app --host \"$APP_HOST\" --port \"$APP_PORT\""]
