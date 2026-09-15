# CosmoMate — Zeabur / Docker
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev

COPY backend/ .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder --chown=app:app /app /app

# Schema + frontend + images (needed when image root is backend/)
COPY --chown=app:app role_case_task_dbeaver.sql /app/role_case_task_dbeaver.sql
COPY --chown=app:app frontend /app/frontend
COPY --chown=app:app mood_img /app/mood_img
COPY --chown=app:app task_img /app/task_img
COPY --chown=app:app img /app/img

USER app

EXPOSE 8080

# Zeabur injects PORT; default 8080 if unset
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
