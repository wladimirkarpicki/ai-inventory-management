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

## 5. Current Project Status (2026-10-19, updated after Phase 4)
- ✅ PHASE 1 (security CI) — MERGED via PR #28
- ✅ vite 8.3.4 + sonner 2.0.8 + vitest 4.1.x migration — MERGED (0509162); Dependabot #22/#23 satisfied
- ✅ PHASE 2 (docker optimization) — MERGED (0509162)
- ✅ PHASE 3 (CI quality green) — MERGED (0684a3b): security.yml fixed, coverage 90% artifact, vitest in CI, pre-commit; CI ALL-GREEN (6/6 jobs) at 0684a3b
- ✅ PHASE 4 (devops) — CLOSED (2026-10-19, user decisions): /api/ready DB-probe, Prometheus /metrics, monitoring compose profile (prometheus v3.15.0 + grafana 13.2.4), backup/monitor scripts, .env.template, .gitattributes LF — MERGED (c5343e2), CI 7/7 green
  - ❌ nginx+SSL — DECLINED by user ("приложение работает локально"); revisit when a domain/production deployment appears
  - ❌ redis — REJECTED, no consumer (YAGNI, user confirmed); revisit trigger: 2+ app replicas (shared login rate-limit/cache)
  - ⏸ external (not blocking): runtime-verify backup.sh/monitor.sh + `--profile monitoring` after user restarts Docker Desktop (daemon down 2026-10-19; CI docker job already builds the image)
- ✅ DB seeded: 23 brands, 1013 products; dashboard overflow fixed
- ⚠️ Docker Desktop on this machine is DOWN ("unable to start", WSL E_NETNAME_DELETED) — local image build/live script run impossible; CI docker job covers image build; re-verify backup.sh/monitor.sh runtime + `--profile monitoring` stack after Docker Desktop restart
- ⚠️ Stray untracked `AGENT_PLAN.md` in workdir AND in ai-delivery-assistant (mojibake duplicates from an earlier session) — DO NOT commit; single source of truth is this file

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

## 6. Next Steps
1. ✅ feat/devops MERGED (c5343e2), CI 7/7 green
2. IN PROGRESS — PHASE 5 Documentation (branch: feat/docs): docs/CI.md (pipeline overview), docs/OPERATIONS.md (runbook: backup/restore, monitoring, health semantics), README update (docker, env.template, pre-commit, coverage, monitoring profile)
3. After Docker Desktop restart: runtime-verify scripts/backup.sh + monitor.sh + monitoring stack
4. Cleanup: delete stale local branches (pr22-test, pr27-test, test-vite-sonner, feat/security-ci, feat/docker-opt, feat/full-ci, feat/devops, feat/docs) after Phase 5 merge + CI green

## 7. Новый запрос = 8 шагов
1. Прочитай план.
2. Определи, как запрос соотносится с планом (новая задача / продолжение / изменение приоритета).
3. Если нужно — создай/обнови задачу в плане.
4. Создай ветку.
5. Выполни.
6. Протестируй.
8. Обнови план.
9. Предложи следующие действия.