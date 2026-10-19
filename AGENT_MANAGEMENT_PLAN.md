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

## 5. Current Project Status (2026-10-19 — 5-PHASE PLAN COMPLETE)
- ✅ PHASE 1 (security CI) — MERGED via PR #28
- ✅ vite 8.3.4 + sonner 2.0.8 + vitest 4.1.x migration — MERGED (0509162); Dependabot #22/#23 satisfied
- ✅ PHASE 2 (docker optimization) — MERGED (0509162)
- ✅ PHASE 3 (CI quality green) — MERGED (0684a3b): security.yml fixed, coverage 90% artifact, vitest in CI, pre-commit
- ✅ PHASE 4 (devops) — CLOSED (user decisions): /api/ready DB-probe, Prometheus /metrics, monitoring compose profile (prometheus v3.15.0 + grafana 13.2.4), backup/monitor scripts, .env.template, .gitattributes LF — MERGED (c5343e2)
  - ❌ nginx+SSL — DECLINED by user ("приложение работает локально"); revisit when a domain/production deployment appears
  - ❌ redis — REJECTED, no consumer (YAGNI, user confirmed); revisit trigger: 2+ app replicas (shared login rate-limit/cache)
- ✅ PHASE 5 (documentation) — MERGED (180bfdb): docs/CI.md (pipeline overview), docs/OPERATIONS.md (runbook), README refresh (Security badge, React 19, Docker section, coverage/vitest/pre-commit)
- ✅ CI state at every merge verified green via GitHub API (last: Tests+Security at 180bfdb)
- ✅ DB seeded: 23 brands, 1013 products; dashboard overflow fixed
- 🎉 ALL 5 PHASES OF THE IMPROVEMENT PLAN ARE COMPLETE. Project enters maintenance mode.
- ⚠️ Open external items: (1) runtime-verify backup.sh/monitor.sh + `--profile monitoring` after Docker Desktop restart (daemon down 2026-10-19, WSL E_NETNAME_DELETED; CI docker job already builds the image); (2) stray untracked `AGENT_PLAN.md` in workdir AND in ai-delivery-assistant (mojibake duplicates) — DO NOT commit; single source of truth is this file; deletion awaits user confirmation

### Phase 4 Evidence (feat/devops)
- pytest 26/26 (new: test_ready_reports_database_up, test_metrics_exposed); mypy/ruff/format green; bandit app-only clean; pip-audit requirements.txt: 0 vulns (incl. new instrumentator dep)
- compose config VALID in base AND `--profile monitoring` modes (SECRET_KEY set)
- Image tags verified via Docker Hub API (lesson applied: no guessed pins): prom/prometheus v3.15.0, grafana/grafana 13.2.4
- Operational design: Dockerfile HEALTHCHECK stays on /api/health (container liveness); compose healthcheck now /api/ready (stack readiness w/ DB probe) — textbook liveness/readiness split
- Incident (repaired): a mangled pwsh path made `ruff --fix` run in the PARENT dir; it touched 5 files in ai-delivery-assistant (import-sort noise) — reverted via `git checkout -- .`, sibling repo clean. Mitigation: always QUOTE `cd "C:\...` paths in pwsh commands

### Phase 3 Evidence (feat/full-ci)
- mypy: `Success: no issues found` (17 targeted `type: ignore`; nosec B105 ×2 on token_type "bearer")
- CI iteration lessons: (1) pin `bandit-sarif-formatter>=1.5.0` was a GUESS — only 1.0.0–1.1.1 exist → `>=1.1.1`; always verify pins with `pip install --dry-run` before pushing; (2) pip-audit has NO `-f sarif` output → JSON artifact instead; upload-artifact latest is v7
- CI state after Phase 3 merge: ALL 6 jobs GREEN (Security: bandit/mypy/ruff/pip-audit; Tests: pytest/docker/frontend)

## 6. Next Steps (maintenance mode)
1. ✅ Plan complete: Phases 1-5 merged, CI green at every step
2. NEW TASKS arrive the usual way: read this plan → branch → work → verify → merge → update plan
3. Scheduled/routine: merge Dependabot PRs (weekly, CI-gated); keep an eye on the weekly Security scan (Mondays 02:00 UTC)
4. One-time after Docker Desktop restart: runtime-verify `scripts/backup.sh`, `scripts/monitor.sh`, and `docker compose --profile monitoring up` (grafana :3000)
5. Optional tidy-up (user confirmation needed): delete stray `AGENT_PLAN.md` duplicates (both projects); old merged `feature/*` local branches (project history, all merged — deletion is cosmetic)

## 7. Новый запрос = 8 шагов
1. Прочитай план.
2. Определи, как запрос соотносится с планом (новая задача / продолжение / изменение приоритета).
3. Если нужно — создай/обнови задачу в плане.
4. Создай ветку.
5. Выполни.
6. Протестируй.
8. Обнови план.
9. Предложи следующие действия.