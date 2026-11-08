FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY ui ./ui
COPY mcp_server ./mcp_server
COPY scripts ./scripts
COPY data/docs ./data/docs
COPY data/users.yaml data/ground_truth.json ./data/

RUN useradd --create-home appuser && mkdir -p /app/state && chown -R appuser /app/state
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
