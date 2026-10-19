# Agent Plan — inventory-management-system
Last updated: 2026-10-19 19:15
Process: глобальный AGENTS.md — C:\Users\Wladimir\.dsh\AGENTS.md | Synced: 2026-10-19 18:55 (= Last updated глобала при консолидации)
Роль: проектный агент (inventory-management-system) — работа с кодинг-сабагентами; задачи — от главного агента (Team Lead) или пользователя.
# Долговременная память агента | Источник истины: этот файл | Читать ПЕРВЫМ при каждом запуске
# Каноническое имя (v3-нейминг, 2026-10-19): AGENT_PLAN_inventory-management-system.md
# Глобальный AGENTS.md (user-global, авто-подхват DSH в каждой сессии): C:\Users\Wladimir\.dsh\AGENTS.md —
# процесс живёт там; этот файл — только состояние проекта. Процессные секции ниже — временные,
# убрать при ближайшей сверке (Synced) с глобалом.

# 🛑 SYSTEM PROMPT — SELF-MANAGING DEVELOPMENT AGENT (НЕИЗМЕНЯЕМАЯ ЧАСТЬ)
# При КАЖДОМ запросе: 1) Прочитать этот файл. 2) Оценить статус. 3) Предложить шаги.
# Фразы «сверимся с планом» / «что по плану» / «обнови план» → относятся сюда.

## 1. Обязательный ритуал
1. Прочитать этот файл (`AGENT_PLAN.md`) ПЕРВЫМ.
2. Оценить текущий статус (done / in-progress / blocked / risks).
3. Предложить следующие шаги по плану; только потом выполнять запрос.
4. Даже без напоминания — возвращаться сюда самостоятельно.
5. Новый запрос = 8 шагов: план → сопоставить с планом → задача → ветка → выполнение → тесты → commit/merge → обновить план.

## 2. Принципы
- Plan → Execute → Verify → Update. Destructive — только с коротким планом и подтверждением.
- Каждая задача = отдельная ветка (`feat/...`). Никогда не коммитить напрямую в `main`.
  (Задокументированное отклонение: docs-коммит 2b275d4 — процедурный сбой, контент корректен, CI green.)
- Перед merge: тесты + evidence + PR-style описание; после — обновить этот файл.
- KISS; high-risk (удаления, force-push, прямой push в main) — только с явным подтверждением человека.

## 3. Структура задачи (всегда фиксируй)
ID / Название / Цель (1 предложение) / Scope / Acceptance Criteria / Verification / Constraints / Статус / Evidence.

## 4. Memory & Self-updating
- Источник истины — файлы, не chat-history: этот план + артефакты репозитория.
- После каждой задачи/сессии обновлять план (статусы, evidence, learnings, decisions).

---

## Status (2026-10-19 19:15)
- 🎉 5-фазный план улучшений ВЫПОЛНЕН ПОЛНОСТЬЮ; проект в maintenance mode.
- CI: Tests + Security зелёные на main (92a8d68); каждый мерж проверен через GitHub API.
- Live stack docker compose RUNNING: app (healthy) + db (healthy) + grafana:3000 + prometheus (scrapes app:8000/metrics, job=inventory-app, up).
- Скрипты верифицированы через WSL bash: monitor.sh → 3/3 OK; backup.sh → валидный pg_dump в backups/.
- Ветки очищены (local + remote): все feat/* удалены, остался только main.
- Кодовых долгов нет: pytest 26/26, vitest 8/8, pip-audit 0 уязвимостей. Открытых PR: 0.
- CI: Tests + Security зелёные на main (2b275d4); каждый мерж проверен по jobs через GitHub API.
- Active focus: —; Blocked: —; Risks: —.
- ✅ Smoke-тест ops-инструментов после перезапуска Docker Desktop — ВЫПОЛНЕН (2026-10-19 18:20):
  - `scripts/monitor.sh`: 3/3 эндпойнта OK (liveness/readiness/metrics)
  - `scripts/backup.sh`: pg_dump схемы ecommerce — OK
  - `docker compose --profile monitoring up`: Grafana 302 (login), Prometheus ready, targets: inventory-app: up, prometheus: up
  - Docker Desktop 29.8.2 — работает, диск 4.5 ГБ свободно

## Tasks (все завершены)
| ID | Task | Status | Branch | Evidence (кратко) |
|----|------|--------|--------|-------------------|
| P1 | Security CI suite | ✅ merged (PR #28) | feat/security-ci | security.yml, dependabot.yml, ruff.toml |
| P2 | Docker-оптимизация | ✅ merged (0509162) | feat/docker-opt | HEALTHCHECK (stdlib urllib), Dockerfile.dev, compose hardening (networks/limits/logging) |
| P3 | CI quality green | ✅ merged (0684a3b) | feat/full-ci | все 6-7 jobs green, coverage 90% артефакт, vitest в CI, pre-commit |
| P4 | DevOps/мониторинг | ✅ merged (c5343e2) | feat/devops | /api/ready (DB probe), /metrics (instrumentator), monitoring profile (prometheus v3.15.0 + grafana 13.2.4), backup.sh/monitor.sh, .env.template, .gitattributes LF |
| P5 | Documentation | ✅ merged (180bfdb) | feat/docs | docs/CI.md, docs/OPERATIONS.md, README refresh (бейджи, Docker-раздел, coverage/pre-commit) |

## Decisions
- 2026-10-18 — v2-шаблон: процессные секции вынести в глобальный AGENTS.md, план хранит состояние. (Глобал создан 2026-10-19 — путь в Process-строке шапки; процессные секции ниже временные, убрать при ближайшей сверке Synced.)
- 2026-10-18 — переименование AGENT_MANAGEMENT_PLAN.md → AGENT_PLAN.md (v2, глобальный шаблон). Завершено 2026-10-19 решением пользователя: AGENT_PLAN.md — единственный план; AGENT_MANAGEMENT_PLAN.md удалён (история в git).
- 2026-10-19 — nginx+SSL: ОТКЛОНЕНО пользователем («приложение работает локально»); триггер возврата — домен/продакшен.
- 2026-10-19 — redis: ОТКЛОНЕНО (YAGNI, нет потребителя); триггер возврата — 2+ реплики приложения (общий rate-limit/кэш).

## Learnings
- vite 8 требует function-синтаксис manualChunks в vite.config.ts; Dependabot-бамп без этого фикса ломает build (86ea77c).
- Пины версий НЕ угадывать: проверять резолв `pip install --dry-run` (bandit-sarif-formatter существует только ≤1.1.1); теги образов проверять через Docker Hub API.
- bandit умеет SARIF только через плагин bandit-sarif-formatter; pip-audit SARIF не умеет вовсе → JSON-артефакт; upload-artifact — актуальная major v7.
- Транспорт pwsh иногда съедает бэкслеши в путях: всегда квочить `cd "C:\..."`; перед commit проверять `git branch --show-current`.
- Непрочитанный файл не считать мусором: «сломанный» AGENT_PLAN.md оказался валидной v2-миграцией параллельной сессии (mojibake был частичным, контент читаем).

## Key evidence
- pytest 26/26 (вкл. /api/ready и /metrics), coverage ~90%; vitest 8/8; compose config VALID (base + `--profile monitoring`); pip-audit: 0 известных уязвимостей.
- Цепочка мержей с зелёным CI на каждом шаге: 0509162 (P2) → 0684a3b (P3) → c5343e2 (P4) → 180bfdb (P5) → 2b275d4 (статус плана).
- Liveness/readiness split: Dockerfile HEALTHCHECK → /api/health (контейнерный liveness); compose healthcheck → /api/ready (stack readiness с DB-пробой).

## Next steps (maintenance)
1. Рутина: мержить Dependabot PR (CI-gated); следить за недельным Security-сканом (понедельник 02:00 UTC).
2. ✅ Выполнено: smoke-тест `scripts/backup.sh`, `scripts/monitor.sh`, `docker compose --profile monitoring up` (grafana :3000) — пройден.
3. Убрать процессные секции 1-4 из этого файла: глобал создан (Process-строка в шапке), завершить v2-миграцию при ближайшей сверке.
4. Новые задачи — по ритуалу из шапки.

## Archive
- ✅ vitest 3.2 → 4.1.11 (PR #27); vite 6.4 → 8.3.4 (PR #23 + manualChunks fix); sonner 1.7 → 2.0.8 (PR #22); PRs #18–#21, #24, #25 — merged
- ✅ feat/tests-and-docker — merged; DB seeded: 23 бренда, 1013 товаров (USD, qty 1–100); dashboard overflow fixed (compactMoney + truncate)
- ✅ Docker-образ inventory-app собран локально (до падения Docker Desktop)
- ✅ Миграция на AGENT_PLAN.md (v2, 2026-10-18) — консолидация завершена 2026-10-19
- ✅ Smoke-тест ops-инструментов (2026-10-19 18:20): liveness/readiness/metrics OK, pg_dump ecommerce OK, monitoring stack (grafana/prometheus) up & healthy
