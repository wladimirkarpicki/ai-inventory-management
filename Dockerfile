# ---- stage 1: build the React SPA ----
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend

# corepack's bundled signature keys cannot verify recent pnpm releases
# ("Cannot find matching keyid" after the signing-key rotation), so
# install pnpm directly with npm instead.
RUN npm install -g pnpm@11

# Lockfile-first layer for dependency caching.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
# tsc -b && vite build -> dist/
RUN pnpm run build

# ---- stage 2: FastAPI runtime serving the built SPA ----
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# psycopg (non-binary) talks to PostgreSQL through libpq.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py database.py schema.sql ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]