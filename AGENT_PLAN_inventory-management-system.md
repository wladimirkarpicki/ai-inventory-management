# Agent Plan — inventory-management-system
Last updated: 2026-10-21 20:14
Process: глобальный AGENTS.md — $DSH_HOME/AGENTS.md | Synced: 2026-10-20 18:48 (= Last updated глобала при последней сверке)
Роль: проектный агент (inventory-management-system) — работа с кодинг-сабагентами; задачи — от главного агента (Team Lead) или пользователя.

## Status
- Active focus: P7 — docker rebuild + смоук (лид, job 20:14); далее P8 (task-3) → P9 CSV-импорт (task-4)
- Blocked: —
- Risks: —

## Tasks
| ID | Task | Status | Branch | AC / Verification | Evidence |
|----|------|--------|--------|-------------------|----------|
| P1 | Security CI suite | ✅ merged (PR #28) | feat/security-ci | `pytest` → exit 0; `ruff check` → exit 0 | security.yml, dependabot.yml, ruff.toml |
| P2 | Docker-оптимизация | ✅ merged (0509162) | feat/docker-opt | `docker build` → exit 0, image < 200MB | optimized Dockerfile |
| P3 | CI quality green | ✅ merged (0684a3b) | feat/full-ci | все 6-7 jobs green, coverage 90% артефакт, vitest в CI, pre-commit | CI config, coverage artifact |
| P4 | DevOps/мониторинг | ✅ merged (c5343e2) | feat/devops | /api/ready → 200; /metrics → 200; compose --profile monitoring up | monitoring profile, backup.sh, .env.template |
| P5 | Documentation | ✅ merged (180bfdb) | feat/docs | docs/CI.md, docs/OPERATIONS.md, README refresh | CI.md, OPERATIONS.md, README |
| P6 | Dashboard analytics + AI forecast | completed (lint+commit) | feat/dashboard-analytics | pytest 37 passed; ruff cleanup done; endpoint JSON verified via curl | DB migration + API endpoints + OpenRouter fallback regression + Dashboard updates + tests all green |
| P7 | Dashboard UX: пагинация + история движений + OpenRouter-фикс | completed (UX+tests+commit) | feat/dashboard-analytics | GET /api/forecast?limit=10&offset=0 → 200 + total; pytest → 0 failed; pnpm build → exit 0; в docker logs видны openrouter-строки | inventory-ux-agent 19:55: GET forecast/rec/movements → 200 (limit/offset/total; days ASC, null в конце; verified vs throwaway DB); stats.low_stock_alerts ≤ 10; pytest 43 passed / 0 failed; ruff 0; pnpm build exit 0; OpenRouter: refine только топ-страницы, маппинг по product_id, timeout 15s, skip/ok/failed-логи (моки в тестах); остаётся lead: docker rebuild + live-логи openrouter в контейнере |
| P8 | Авто-запись stock_movements при реальных операциях | pending (board task-3) | feat/auto-movements | PATCH qty → движение в той же транзакции; pytest → 0 failed | утверждён пользователем 19:48; спека на board |
| P9 | CSV-импорт товаров | pending (board task-4) | TBD (Lead) | POST /api/products/import → imported/skipped/errors; pytest → 0 failed | запрос пользователя 19:48; после P8 |
| P10 | Reorder point + lead_time_days | pending | TBD | миграция 002; restock = rate×lead×1.1; pytest → 0 failed | роадмап, утверждён 19:48 |
| P11 | Кэш прогноза (TTL 5–15 мин) | pending | TBD | повторный GET forecast без пересчёта (кэш-хит) | роадмап, утверждён 19:48 |
| P12 | CSV-экспорт движений | pending | TBD | GET /api/movements/export → text/csv | роадмап, утверждён 19:48 |
| P13 | Rate-limit OpenRouter (кэш refine, 429-fallback) | pending | TBD | 429 → regression fallback + лог | роадмап, утверждён 19:48 |
| P14 | Графики динамики (recharts — новая dep) | pending | TBD | pnpm build exit 0 с recharts | роадмап, утверждён 19:48 |

## Decisions
- 2026-10-18 — v2-шаблон: процессные секции вынести в глобальный AGENTS.md, план хранит состояние. (Глобал создан 2026-10-19 — путь в Process-строке шапки; процессные секции ниже временные, убрать при ближайшей сверке Synced.)
- 2026-10-18 — переименование AGENT_MANAGEMENT_PLAN.md → AGENT_PLAN.md (v2, глобальный шаблон). Завершено 2026-10-19 решением пользователя: AGENT_PLAN.md — единственный план; AGENT_MANAGEMENT_PLAN.md удалён (история в git).
- 2026-10-19 — nginx+SSL: ОТКЛОНЕНО пользователем («приложение работает локально»); триггер возврата — домен/продакшен.
- 2026-10-19 — redis: ОТКЛОНЕНО (YAGNI, нет потребителя); триггер возврата — 2+ реплики приложения (общий rate-limit/кэш).
- 2026-10-21 — OpenRouter: ТОЛЬКО free models router (`openrouter/free`) — директива пользователя; verified .env (L8) / compose.yml (L40) / main.py (L876).
- 2026-10-21 — Утверждено пользователем: P8 (авто-запись движений) + P9 (CSV-импорт) — на board (task-3/task-4); роадмап P10–P14: reorder point, кэш прогноза, CSV-экспорт, rate-limit OpenRouter, графики recharts (новая dep одобрена явно).

## Learnings
- 2026-10-20 — Инфраструктура: Docker Desktop (WSL2) на внешнем накопителе D: (junction) — см. `ENVIRONMENT.md` (раздел Infra / Machine).
- vite 8 требует function-синтаксис manualChunks в vite.config.ts; Dependabot-бамп без этого фикса ломает build (86ea77c).
- Пины версий НЕ угадывать: проверять резолв `pip install --dry-run` (bandit-sarif-formatter существует только ≤1.1.1); теги образов проверять через Docker Hub API.
- bandit умеет SARIF только через плагин bandit-sarif-formatter; pip-audit SARIF не умеет вовсе → JSON-артефакт; upload-artifact — актуальная major v7.
- Транспорт pwsh иногда съедает бэкслеши в путях: всегда квочить `cd "C:\..."`; перед commit проверять `git branch --show-current`.
- Непрочитанный файл не считать мусорным: «сломанный» AGENT_PLAN.md оказался валидной v2-миграцией параллельной сессии (mojibake был частичным, контент читаем).
- 2026-10-20 — `seed_demo_data.py` с хоста (DATABASE_HOST=localhost) пишет в нативный Windows-PostgreSQL на 5432 (postgresql-x64-18); контейнерный db не публикует наружу — его нужно заполнять через `docker compose exec app python -m scripts.seed_demo_data --force`.
- 2026-10-21 — Хостовая dev-БД (localhost/ecommerce) не имеет таблицы stock_movements (миграция 001 применена только в контейнере): хостовой запуск приложения упадёт на /api/forecast до применения миграции; AC-проверки гонять через throwaway-БД (паттерн conftest).
- 2026-10-21 — delegation depth в сессии исчерпан (subagent-вызовы запрещены средой): проектный агент выполнил P7 сам — последовательные мелкие срезы с верификацией после каждого; паттерн признан рабочим для больших задач.

## Next steps (maintenance)
1. Рутина: мержить Dependabot PR (CI-gated); следить за недельным Security-сканом (понедельник 02:00 UTC).
2. ✅ Выполнено: smoke-тест `scripts/backup.sh`, `scripts/monitor.sh`, `docker compose --profile monitoring up` (grafana :3000) — пройден.
3. Новые задачи — по ритуалу из шапки.

## Archive
- ✅ vitest 3.2 → 4.1.11 (PR #27); vite 6.4 → 8.3.4 (PR #23 + manualChunks fix); sonner 1.7 → 2.0.8 (PR #22); PRs #18–#21, #24, #25 — merged
- ✅ feat/tests-and-docker — merged; DB seeded: 23 бренда, 1013 товаров (USD, qty 1–100); dashboard overflow fixed (compactMoney + truncate)
- ✅ Docker-образ inventory-app собран локально (до падения Docker Desktop)
- ✅ Миграция на AGENT_PLAN.md (v2, 2026-10-18) — консолидация завершена 2026-10-19
- ✅ Smoke-тест ops-инструментов (2026-10-19 18:20): liveness/readiness/metrics OK, pg_dump ecommerce OK, monitoring stack (grafana/prometheus) up & healthy
- ✅ Контейнерная БД заполнена 2026-10-20 через `docker compose exec app python -m scripts.seed_demo_data --force` — 20 бренда / 1004 товаров (in-container); вчерашний хостовый seed ушёл в нативный Windows-PostgreSQL на localhost:5432 (postgresql-x64-18), контейнерный db не公開ез наружу; restart app healthy, / и /api/health → 200, users=1
- ✅ P7 (2026-10-21) — Dashboard UX: GET-пагинация forecast/recommendations/movements (limit/offset/total), Recent movements в UI, топ-10 low_stock_alerts, OpenRouter-фикс (top-page refine, product_id-маппинг, логи, compose env), N+1 → батч, 9999 → null, seed_movements на get_connection_string; pytest 43 green (feat/dashboard-analytics)
