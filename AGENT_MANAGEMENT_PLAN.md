# AGENT MANAGEMENT PLAN — Inventory Management System
# ЯНЧ/Долговременная память агента | Авто-напоминание ОБЯЗАТЕЛЬНО
# Источник истины: этот файл. Читать ПЕРВЫМ при каждом запуске.
# Ссылка на план реализации: INVENTORY_PLAN.md (теперь интегрирован ниже)
# Системная инструкция агента (обязательная): вставлена в блок ниже

# 🛑 SYSTEM PROMPT — SELF-MANAGING DEVELOPMENT AGENT (НЕИЗМЕНЯЕМАЯ ЧАСТЬ)
# При КАЖДОМ запросе: 1) Прочитать этот файл. 2) Оценить статус. 3) Предложить шаги.
# Фразы «давай сверимся с планом» / «что по плану» / «обнови план» → относится сюда.

## 1. Обязательный ритуал
1. Прочитать `AGENT_MANAGEMENT_PLAN.md` (и INVENTORY_PLAN.md).
2. Кратко оценить текущий статус (done / in-progress / blocked / risks).
3. На основе плана предложить следующие шаги.
4. Только потом выполнять запрос.
5. Даже без напоминания — сам возвращаться сюда.

## 2. Принципы
- Plan → Execute → Verify → Update (всегда с коротким планом, особенно destructive).
- Каждая задача = отдельная ветка (`feature/<id>` или `ai/<id>`).
- Только в ветке (worktree предпочтительно). Никогда не коммитить напрямую в `main`.
- Перед merge: тесты + evidence + PR-style описание.
- После выполнения — обновить `AGENT_MANAGEMENT_PLAN.md`.
- KISS; high-risk только с явным подтверждением человека.

## 3. Структура задачи (всегда фиксируй)
- ID / Название / Цель (1 предложение) / Scope / Acceptance Criteria / Verification / Constraints / Статус / Evidence.

## 4. Memory & Self-updating
- Durable решения в файлах (`AGENT_MANAGEMENT_PLAN.md`, `INVENTORY_PLAN.md`, `AGENTS.md`).
- После сессии / задачи обновлять файл.
- Не полагаться на chat-history; файлы — источник истины.

## 5. Current Project Status (2026-10-18, updated after Phase 2)
- ✅ PR #27 (vitest 3.2 → 4.1.11) — MERGED, tests pass
- ✅ PRs #18, #19, #20, #21, #24, #25 — MERGED
- ✅ feat/tests-and-docker — MERGED
- ✅ PHASE 1 (security CI) — MERGED via PR #28 (security.yml + dependabot + ruff.toml + dev deps)
- ✅ vite 6.4 → 8.3.4 + sonner 1.7 → 2.0.8 migration — integrated into `feat/docker-opt` (merge f9bf5c1); supersedes Dependabot PRs #22/#23 (close them after merge)
- ✅ PHASE 2 (docker optimization) — DONE on `feat/docker-opt` (e7b55a4), awaiting PR merge
- ✅ DB seeded: 23 brands, 1013 products, USD prices, qty 1-100
- ✅ Dashboard overflow fixed (compactMoney + truncate)
- ✅ Docker image inventory-app built locally

### Phase 2 Evidence (feat/docker-opt, commit e7b55a4)
- Dockerfile: HEALTHCHECK via python urllib (slim image has no curl), non-root appuser, multi-stage
- Dockerfile.dev: NEW dev image — hot reload (--reload), dev deps, devuser
- compose.yml: `backend` network, restart: unless-stopped, cpu/memory limits (0.5 CPU / 512M), json-file logging caps (10m × 3), app healthcheck (python urllib), db healthcheck kept
- Verification: `docker compose config` VALID · pytest 24/24 · `pnpm install --frozen-lockfile` in-sync · `pnpm run build` ✓ (vite 8.3.4, 2.94s) · vitest 8/8

### Branch state
- local `main` is STALE (diverged, pre-Phase-1): after merging feat/docker-opt PR, reset local main to origin/main (`git fetch && git checkout main && git reset --hard origin/main`)
- ⚠️ Known issue: `/api/health` is liveness-only (no DB probe) — candidate improvement for Phase 4

## 6. Next Steps
1. Merge PR `feat/docker-opt` → main (contains: vite-8/sonner migration + Phase 2 docker work)
2. Close Dependabot PRs #22 + #23 (superseded by the migration in feat/docker-opt)
3. Reset local main to origin/main after merge
4. PHASE 3 — Enhanced CI Pipeline (branch: feat/full-ci): pre-commit, coverage, integration tests
5. PHASE 4 — DevOps & Monitoring (branch: feat/devops): nginx, redis, prometheus, grafana, backup scripts
6. PHASE 5 — Documentation (branch: feat/docs): CI.md, runbooks

## 7. Новый запрос = 8 шагов
1. Прочитай план.
2. Определи, как запрос соотносится с планом (новая задача / продолжение / изменение приоритета).
3. Если нужно — создай/обнови задачу в плане.
4. Создай ветку.
5. Выполни.
6. Протестируй.
8. Обнови план.
9. Предложи следующие действия.