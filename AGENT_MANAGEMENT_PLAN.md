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

## 5. Current Project Status (2026-10-18)
- ✅ PR #27 (vitest 3.2 → 4.1.11) — MERGED, tests pass
- ✅ PR #23 (vite 6.4 → 8.3.4) — BUILD FIXED (vite.config.ts manualChunks function), tests pass
- ✅ PR #22 (sonner 1.7 → 2.0.8) — BUILD FIXED, tests pass
- ✅ PRs #18, #19, #20, #21, #24, #25 — MERGED
- ✅ feat/tests-and-docker — MERGED
- ✅ DB seeded: 23 brands, 1013 products, USD prices, qty 1-100
- ✅ Dashboard overflow fixed (compactMoney + truncate)
- ✅ Docker image inventory-app built locally
- 🔄 Next: Merge PR #22 + #23 to main, then Phase 2/3

## 6. Новый запрос = 8 шагов
1. Прочитай план.
2. Определи, как запрос соотносится с планом (новая задача / продолжение / изменение приоритета).
3. Если нужно — создай/обнови задачу в плане.
4. Создай ветку.
5. Выполни.
6. Протестируй.
8. Обнови план.
9. Предложи следующие действия.