# Agent Plan — inventory-management-system
Last updated: 2026-10-24 16:20
Process: глобальный AGENTS.md — $DSH_HOME/AGENTS.md | Synced: 2026-10-24 13:00 (= Last updated глобала при последней сверке)
Роль: проектный агент (inventory-management-system) — работа с кодинг-сабагентами; задачи — от главного агента (Team Lead) или пользователя.

## Status
- Active focus: P24 (демо-данные) + P25 (Orders) слиты в main (941c049, 2e05842); миграция 004 применена к live-БД; контейнер пересобирается; ждём фидбэка + новые предложения отправлены пользователю
- Blocked: —
- Risks: дубли товаров ИСПРАВЛЕНЫ (P18: 2008→1004, UNIQUE(brand_id, lower(name))); бэкап до дедупа — backup_before_dedupe.sql (не в git); Docker data disk чинился e2fsck 23.10 — при повторных падениях демона см. ENVIRONMENT.md

## Tasks
| ID | Task | Status | Branch | AC / Verification | Evidence |
|----|------|--------|--------|-------------------|----------|
| P1 | Security CI suite | ✅ merged (PR #28) | feat/security-ci | `pytest` → exit 0; `ruff check` → exit 0 | security.yml, dependabot.yml, ruff.toml |
| P2 | Docker-оптимизация | ✅ merged (0509162) | feat/docker-opt | `docker build` → exit 0, image < 200MB | optimized Dockerfile |
| P3 | CI quality green | ✅ merged (0684a3b) | feat/full-ci | все 6-7 jobs green, coverage 90% артефакт, vitest в CI, pre-commit | CI config, coverage artifact |
| P4 | DevOps/мониторинг | ✅ merged (c5343e2) | feat/devops | /api/ready → 200; /metrics → 200; compose --profile monitoring up | monitoring profile, backup.sh, .env.template |
| P5 | Documentation | ✅ merged (180bfdb) | feat/docs | docs/CI.md, docs/OPERATIONS.md, README refresh | CI.md, OPERATIONS.md, README |
| P6 | Dashboard analytics + AI forecast | completed (lint+commit) | feat/dashboard-analytics | pytest 37 passed; ruff cleanup done; endpoint JSON verified via curl | DB migration + API endpoints + OpenRouter fallback regression + Dashboard updates + tests all green |
| P7 | Dashboard UX: пагинация + история движений + OpenRouter-фикс | completed (UX+tests+commit) | feat/dashboard-analytics | GET /api/forecast?limit=10&offset=0 → 200 + total; pytest → 0 failed; pnpm build → exit 0; в docker logs видны openrouter-строки | inventory-ux-agent 19:55: GET forecast/rec/movements → 200 (limit/offset/total; days ASC, null в конце; verified vs throwaway DB); stats.low_stock_alerts ≤ 10; pytest 43 passed / 0 failed; ruff 0; pnpm build exit 0; OpenRouter: refine только топ-страницы, маппинг по product_id, timeout 15s, skip/ok/failed-логи (моки в тестах); LEAD LIVE 22:26: контейнер eb0c8b4, openrouter-логи refining → «ok, refined 10»; free-пул лотерейный (1/3 вызовов refine, остальные — штатный fallback); ai_refined=true в ответах, пример: restock 77→10 (Coffee-Mate, qty=5) |
| P8 | Авто-запись stock_movements при реальных операциях | completed (auto+tests+commit) | feat/auto-movements | PATCH qty → движение в той же транзакции; pytest → 0 failed | inventory-ux-agent 21:55: POST → in 'initial' (только qty>0); PATCH delta → in/out, reason из payload или manual_edit; без изменения qty → движения нет; атомарность — rollback при падении INSERT (тест с raise_server_exceptions=False); DELETE товара чистит его движения (FK, та же транзакция); UI: Reason for change (Correction/Restock/Sale/Write-off); + P7.1-хотфикс: толерантный парсинг OpenRouter content (_extract_json_array: strip/fence/[ … ]); pytest 53 passed / 0 failed; ruff 0; pnpm build exit 0; LEAD LIVE 22:26: PATCH +1 restock → движение #31 (in/+1/restock) в GET /api/movements мгновенно; restore → #32 (out/−1/correction) |
| P9 | CSV-импорт товаров | completed (import+tests+commit) | feat/csv-import | POST /api/products/import → imported/skipped/errors; pytest → 0 failed | inventory-ux-agent 22:55: multipart .csv (utf-8-sig/BOM, ≤1MB, ≤1000 строк), маппинг колонок по именам заголовка (лишние игнорируются); валидные → INSERT + движение in 'import' (qty>0) одной транзакцией (P8-паттерн); дубликаты (БД + внутри файла, case-insensitive name+brand) → skipped; битые → errors с 1-based номером строки данных; unknown brand → errors; UI: Import CSV + диалог-сводка + CSV template (client blob); AC 3+1+1 → imported=3/skipped=1/errors=1 зелёный; pytest 64 passed / 0 failed; ruff 0; pnpm build (tsc -b && vite build) exit 0; P9.1-ХОТФИКС: container crash-loop пойман live-смоуком лида 23:51 — FastAPI требует python-multipart при РЕГИСТРАЦИИ роута с UploadFile (startup, не request-time); host-тесты не ловили (пакет есть глобально на хосте); фикс — python-multipart>=0.0.32 в requirements.txt (резолв pip dry-run = 0.0.32), pytest 64 green после фикса; LEAD LIVE 01:15: контейнер healthy; POST /api/products/import → 200 {imported:2, skipped:[{row:3,duplicate}], errors:[{row:4,invalid price}]} — AC точен; движение #33 (in/+5/'import') записано автоматически (P8-интеграция); cleanup DELETE 2009/2010 → 200 ok, движения очищены автоматически |
| P10 | Reorder point + lead_time_days | completed (branch pushed) | feat/reorder-point (ff33e29) | миграция 002; restock = rate×lead×1.1; pytest → 0 failed | миграция 002 (reorder_point=10, lead_time_days=7) + schema.sql + ProductIn; _forecast_for_product/forecast/recommendations на per-product rp/lt; restock = rate×lead×1.1, target = max(qty+needed, rp); API продуктов: SELECT/INSERT/UPDATE/return с rp/lt; UI ProductsPage: форма + колонки + api.ts Product; тесты под новую логику (15 вместо 31, total=2 в urgency); pytest 64/0, ruff 0, pnpm build OK; ветка от main 7905fef, запушена |
| P11 | Кэш прогноза (TTL 10 мин) | completed (branch pushed) | feat/forecast-cache (4a31d66) | повторный GET forecast без пересчёта (кэш-хит) | _forecast_cache in-memory + FORECAST_CACHE_TTL_SECONDS=600; кэш-хит отдаёт срез без БД и без OpenRouter; refine только на промахе ( dicts общие с кэшем ); инвалидация на POST/PATCH/DELETE /api/products и CSV-import; conftest autouse _reset_forecast_cache; +3 теста (hit skips recompute / write invalidates / TTL expire); pytest 67/0, ruff 0, pnpm build OK; ветка стакнута на feat/reorder-point |
| P12 | CSV-экспорт движений | ✅ merged (11c7adf) | feat/movements-export (bc0c542) | GET /api/export/movements.csv → text/csv | GET /api/export/movements.csv (auth, text/csv, attachment, newest-first, колонки как в movements API); кнопка Export CSV в Recent movements (authed blob); +3 теста (401/контент-порядок/пустая история); pytest 70/0, ruff 0, pnpm build OK |
| P13 | Rate-limit OpenRouter (429-fallback) | ✅ merged (6aac90f) | feat/openrouter-ratelimit (cb8bf49) | 429 → regression fallback + лог | _openrouter_state cooldown 5 мин, на 429 армируется (лог rate-limited ... cooling down); внутри окна refine пропускается целиком (лог cooldown active) — без retry-storm в free-pool; прочие HTTPError → прежний failed-лог; conftest-reset cooldown; +2 теста (429 arms cooldown, second GET без urlopen-вызова; экспирация → refine resumes); pytest 72/0, ruff 0, pnpm build OK |
| P15 | Dashboard tabs UI | ✅ merged (14ba179) | feat/dashboard-tabs (ac5e8ba) | 4 таба (Forecast/Rec/Dynamics/Movements), ленивая загрузка, честные тексты | табы в хедере дашборда; lazy loading по табам; честный текст «forecast service unreachable»; pytest 78/0, ruff 0, pnpm build OK | frontend/src/pages/DashboardPage.tsx (tabs, lazy loading, ARIA), main.py (нет изменений), tests (нет новых — ленивая загрузка покрыта существующими тестами) |
| P16 | Low stock таб + UI polish дашборда | ✅ merged (1616e9e) | feat/dashboard-ui-polish (313c61b) | pytest 0 failed; pnpm build OK | 5-й таб Low stock с бейджем количества (секция над табами удалена); убраны дубль-h3 внутри всех панелей; фикс stray-запятой после forecast-панели (рендерилась как лишний элемент); empty-state для Dynamics; low_stock_alerts: сабквери-дедуп + ORDER BY quantity ASC (восстановлен порядок срочности, сломанный c0571b2 — поймал тест capped_at_top10); pytest 78/0, ruff 0, pnpm build OK |
| P17 | UI polish v2 | ✅ merged (de19e50) | feat/dashboard-ui-polish-2 (1b28502) | pnpm build OK | убран theme-toggle из хедера (найден «stepper ▲▼» — иконка ☀ в мелком размере); убран бейдж-счётчик с таба Low stock; пагинация 15/таб; Stock dynamics 600px + сводка (in/out/net/active days) + период 30/90 + Legend + короткие даты; фикс дубля daily-useEffect (двойной fetch) |
| P18 | Чистка дублей товаров + UNIQUE(brand, lower(name)) | ✅ merged (5800a00) | feat/dedupe-products (1f5858d) | `pytest` → 0 failed; `GET /api/products` → 1004 items | миграция 003 (DELETE лузеров + их движения + индекс); schema.sql + сид ON CONFLICT; API create/update → 400 при дубле; live: 2008→1004 товаров, low_stock 98→49, dup-групп 0; pytest 81/0, ruff 0 |
| P19 | Low stock: полная пагинация | ✅ merged (af21660) | feat/low-stock-pagination (b9ee3c2) | `GET /api/low-stock?limit=5&offset=10` → 2 items, total 12 | GET /api/low-stock (qty ASC, reorder_point в ответе); таб Low stock → Pager + колонка Reorder point; +3 теста; pytest 84/0, ruff 0, pnpm build OK |
| P20 | Products UX: фильтр + сортировка по колонкам + стр. 15 | ✅ merged (8ed9c03) | feat/products-ux (f3ea106) | `GET /api/products?low_stock_only=true` → только qty<rp; `pnpm test` → 0 failed | бекенд: low_stock_only, SORT_COLUMNS +rp/lt, PAGE_SIZE 15; UI: toggle «Below reorder point», кликабельные заголовки со стрелкой направления (Select+direction убраны); live: 15/стр, 67 страниц, 101 позиция ниже rp, 0 нарушений |
| P21 | Forecast: stock/rp/lt/AI-бейдж в таблице | ✅ merged (493830e) | feat/forecast-badges (f07e7c4) | forecast rows содержат reorder_point/lead_time_days | строки прогноза несут rp/lt (кнопки расчёта); UI: колонки Stock/Reorder point/Lead time + бейдж «AI» у LLM-уточнённых строк; live: ключи в ответе подтверждены |
| P22 | vitest для дашборда | ✅ merged (d4fd531) | feat/ui-tests (9563001) | `pnpm test` → 12 passed / 0 failed | DashboardPage.test.tsx: 5 табов, ленивая загрузка, пейджер (диапазоны + disabled), колонки low-stock; мок @/api по URL, ResizeObserver-stub |
| P23 | Stock dynamics v2 + скроллбар-степпер + порядок хедера | ✅ merged (1690ca0) | feat/dynamics-revamp (1e47712) | `pytest` → 88/0; `pnpm test` → 12/12 | «степпер ▲▼» = скроллбар overflow-x-auto (двигал табы) → табы теперь переносятся (flex-wrap), хедер тоже; Brands перед Products; Dynamics: под-табы Flow (ComposedChart + 7-дн. скользящее среднее, KPI + Avg daily out + Peak day) / Top movers (GET /api/movements/top, два топ-10) / Daily detail (net + cumulative); +3 теста эндпоинта |
| P24 | Живые демо-данные | ✅ merged (941c049) | feat/demo-vitality (1830a8c) | seeders обновлены | seed_movements.py: профили спроса (30/50/20%), 30 дней, --wipe; seed_demo_data: rp 5–30, lt 3–14; live: 1004 товара пере-порогованы, 7787 движений |
| P25 | Orders: закупки со сквозной интеграцией | ✅ merged (2e05842) | feat/orders (c8792f6) | `pytest` → 95/0 | миграция 004; POST/GET /api/orders + receive/cancel; приёмка: сток + движение purchase_order + инвалидация кэша одной транзакцией; 6-й таб Orders (бейджи ordered/overdue/received/cancelled, Receive/Cancel, диалог с typeahead); кнопки Order в Recommendations и Low stock; +7 тестов; live-БД: таблица orders создана |

## Task details (нетривиальные)

### P18 — Чистка дублей + UNIQUE(brand, lower(name))
Goal: убрать задвоенные товары (двойной сид) и запретить дубли на уровне БД.
Scope: migrations/003 (DELETE лузер-строк + их stock_movements, UNIQUE-индекс), schema.sql, seed ON CONFLICT DO NOTHING, API create/update → 400 при (brand, lower(name))-коллизии, 3 теста.
AC: `pytest` → 0 failed; после live-миграции `SELECT COUNT(*) FROM products` = 1004, dup-групп = 0.
Verification: `python -m pytest tests/` → 81 passed; `docker compose exec db psql ... -c "SELECT COUNT(*) FROM products"` → 1004.
Constraints: деструктивная миграция — подтверждена пользователем (P18 → P19 по списку); бэкап pg_dump до применения; keeper = строка с меньшим id (свой movement-хвост сохраняется).

### P19 — Low stock: полная пагинация
Goal: таб Low stock показывает ВСЕ позиции ниже порога с пагинацией (было top-10 из stats).
Scope: GET /api/low-stock (limit/offset, qty ASC, DISTINCT ON (brand, lower(name)), reorder_point в items); фронт: состояние lowStockPage/Offset, эффект по табу, колонка Reorder point, Pager; +3 теста.
AC: `GET /api/low-stock?limit=5&offset=10` при 12 позициях → 2 items, total 12; `pytest` → 0 failed.
Verification: `python -m pytest tests/test_analytics.py` → все green; `pnpm build` → exit 0.
Constraints: эндпоинт размещён после analytics-констант (Query-дефолт вычисляется при декорации); stats.low_stock_alerts остаётся для совместимости тестов.

### P20 — Products UX (фильтр, сортировка заголовками, страница 15)
Goal: быстрый фильтр «ниже reorder point», сортировка кликом по заголовкам, единый размер страницы 15.
Scope: бекенд — low_stock_only-параметр (quantity < reorder_point, NULL excluded), SORT_COLUMNS += reorder_point/lead_time_days, PAGE_SIZE 10→15; UI — toggle-кнопка вместо Select+direction, SortHead-кнопки в заголовках; тесты пагинации адаптированы (32→3 страницы), +1 тест фильтра/сортировки.
AC: `pytest` → 0 failed; `GET /api/products?low_stock_only=true` → все items удовлетворяют qty<rp.
Verification: `python -m pytest tests/` → 85 passed; live-смоук: 101/101 ниже rp, 0 нарушений.
Constraints: NULL-quantity исключаются из фильтра; клик по активному столбцу переключает направление.

### P21 — Forecast: rp/lt/AI в таблице
Goal: показать параметры расчёта (reorder_point, lead_time_days) и честную LLM-метку в прогнозе.
Scope: main.py — два поля в строках forecast; UI — колонки Stock/Reorder point/Lead time + бейдж «AI»; структурный тест расширен.
AC: forecast-строки содержат reorder_point/lead_time_days; `pytest` → 0 failed.
Verification: `GET /api/forecast?limit=1` → ключи в ответе; `pnpm build` → exit 0.
Constraints: кэш P11 не затронут (поля добавлены до кэширования списка); бейдж только при ai_refined=true.

### P22 — vitest для дашборда
Goal: UI-регрессии (табы, ленивость, пейджер) ловятся на этапе тестов, а не в браузере.
Scope: DashboardPage.test.tsx — 4 теста; мок @/api per-URL; ResizeObserver-stub для recharts.
AC: `pnpm test` → 0 failed (12 тестов в 5 файлах).
Verification: `pnpm test` → 12 passed.
Constraints: Recharts-график не тестируется (обход — не открываем Dynamics-таб в тестах).

### P23 — Stock dynamics v2 + скроллбар-степпер + порядок хедера
Goal: убрать «степпер» (скроллбар overflow-x-auto в строке табов, двигавший табы), сделать Dynamics информативной (под-табы, больше метрик), поменять порядок кнопок хедера.
Scope: nav flex-wrap в DashboardPage и layout (скроллбары исчезают), Brands перед Products; Dynamics: под-табы Flow/Top movers/Daily detail, ComposedChart + линия 7-дн. среднего, KPI Avg daily out + Peak day; бекенд GET /api/movements/top (лидерборды in/out за окно); +3 теста.
AC: `pytest` → 0 failed; `pnpm test` → 0 failed; таб-навигация не скроллится.
Verification: `python -m pytest tests/` → 88 passed; `pnpm test` → 12 passed; `pnpm build` → exit 0.
Constraints: recharts ComposedChart вместо BarChart (Line поверх баров); rolling average и cumulative считаются на клиенте из daily-данных; pg_dump-бэкап держать вне git (.gitignore).

### P24 — Живые демо-данные
Goal: наполнить демо-БД реалистичной историей движений и разнообразить пороги, чтобы прогнозы/динамика/лидерборды показывали осмысленные данные.
Scope: seed_movements.py переписан (профили спроса 30/50/20% + restock-волны + write-offs, --wipe); seed_demo_data.py добавляет rp 5–30 / lt 3–14; к live-БД: UPDATE порогов + прогон сидера.
AC: после прогона — у большинства товаров есть тренд (Days left не N/A); rp/lt различаются.
Verification: `SELECT COUNT(*) FROM stock_movements` → ~7787; визуально Forecast/Dynamics.
Constraints: чистка старых движений только через --wipe (явный флаг); продукт-количества не трогаются.

### P25 — Orders (закупки)
Goal: полный цикл закупки: заказ → (приёмка | отмена), интегрированный со стоком, движениями, кэшем прогноза и UI.
Scope: миграция 004 (orders: status ordered/received/cancelled, expected_at, индекс); API: create (expected из lead_time), list (пагинация+фильтр статуса, JOIN имени), receive (сток + purchase_order-движение + инвалидация кэша, одна транзакция), cancel; UI: 6-й таб Orders (бейджи, overdue, Receive/Cancel, диалог New order с typeahead), кнопки Order в Recommendations (rec. qty) и Low stock (до reorder point); +7 бекенд-тестов; vitest 6 табов.
AC: `pytest` → 0 failed; receive → quantity вырос, движение записано, повторный receive → 400.
Verification: `python -m pytest tests/test_api.py` → все green; live-смоук после деплоя.
Constraints: received — терминальный статус (отменить нельзя); приёмка меняет данные → обязательная инвалидация кэша прогноза; заказы без supplier-сущности (бренд = поставщик de facto).

## Decisions
- 2026-10-18 — v2-шаблон: процессные секции вынести в глобальный AGENTS.md, план хранит состояние. (Глобал создан 2026-10-19 — путь в Process-строке шапки; процессные секции ниже временные, убрать при ближайшей сверке Synced.)
- 2026-10-18 — переименование AGENT_MANAGEMENT_PLAN.md → AGENT_PLAN.md (v2, глобальный шаблон). Завершено 2026-10-19 решением пользователя: AGENT_PLAN.md — единственный план; AGENT_MANAGEMENT_PLAN.md удалён (история в git).
- 2026-10-19 — nginx+SSL: ОТКЛОНЕНО пользователем («приложение работает локально»); триггер возврата — домен/продакшен.
- 2026-10-19 — redis: ОТКЛОНЕНО (YAGNI, нет потребителя); триггер возврата — 2+ реплики приложения (общий rate-limit/кэш).
- 2026-10-21 — OpenRouter: ТОЛЬКО free models router (`openrouter/free`) — директива пользователя; verified .env (L8) / compose.yml (L40) / main.py (L876).
- 2026-10-21 — Утверждено пользователем: P8 (авто-запись движений) + P9 (CSV-импорт) — на board (task-3/task-4); роадмап P10–P14: reorder point, кэш прогноза, CSV-экспорт, rate-limit OpenRouter, графики recharts (новая dep одобрена явно).
- 2026-10-21 — P8 (подтверждено лидом): ветка feat/auto-movements от feat/dashboard-analytics; английские лейблы причин Restock/Sale/Write-off/Correction → restock/sale/write_off/manual_edit; qty=0 при создании → без движения («In +0» — мусор).
- 2026-10-21 — P8: qty в stock_movements хранится ЗНАКОВЫМ (out → отрицательный), а не |delta| из буквенной спеки task-3 — конвенция схемы (миграция 001: «positive or negative depending on in_out»), аналитика (_daily_series суммирует qty напрямую) и сиды/P7-тесты уже знаковые; |delta| делал бы out-движения «ростом» в прогнозе.
- 2026-10-21 — P8: DELETE товара удаляет его движения в той же транзакции — FK без CASCADE блокировал бы удаление (падал существующий тест test_product_update_and_delete); история уходит вместе с товаром.
- 2026-10-21 — P9 (подтверждено лидом 22:20): ветка feat/csv-import от feat/auto-movements (eb0c8b4); цепочка P7→P8→P9, мерж всей цепочки — с пользователем в конце; row в skipped/errors = 1-based номер строки данных (заголовок=0); дубликаты (name+brand) и бренд-lookup case-insensitive; header-only → 400 как «пустой»; лишние колонки CSV игнорируются.

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
- 2026-10-21 — free-pool reasoning-модели OpenRouter кладут CoT-текст/markdown-фенсы в message.content ПЕРЕД JSON — парсить толерантно (strip → снять ```-фенсы → извлечь срез [ … ] по find/rfind), см. _extract_json_array в main.py (P7.1-хотфикс, по смоук-логам контейнера).
- 2026-10-21 — FastAPI проверяет python-multipart при РЕГИСТРАЦИИ роута с UploadFile (ensure_multipart_is_installed, routing.py → analyze_param → startup) — контейнер уходит в crash-loop; host-тесты этого НЕ ловят, если пакет есть глобально на хосте; requirements.txt — единственный источник зависимостей (P9.1-хотфикс).

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
- ✅ P8 + P7.1 (2026-10-21) — авто-запись движений: POST → initial, PATCH → delta с reason (одна транзакция, rollback-тест), DELETE чистит движения; UI Reason for change; OpenRouter-хотфикс _extract_json_array (fence/prose/мусор); pytest 53 green (feat/auto-movements)
- ✅ P9 (2026-10-21) — CSV-импорт: POST /api/products/import (гварды 1MB/1000 строк/utf-8-sig, маппинг по заголовку, дубликаты БД+файл, import-движения одной транзакцией), Import CSV + шаблон в UI; pytest 64 green (feat/csv-import)
- ✅ P10 (2026-10-22) — reorder point + lead_time_days per-product: миграция 002, restock = rate×lead×1.1 с target≥rp, рекомендации на per-product порогах, API+UI ProductsPage; pytest 64/0 (feat/reorder-point, ff33e29)
- ✅ P11 (2026-10-22) — кэш прогноза in-memory TTL 10 мин: хит без БД/OpenRouter, refine на промахе, инвалидация на всех записях товаров, conftest-reset; pytest 67/0 (feat/forecast-cache, 4a31d66, стакнуто на P10)
- ✅ P12 (2026-10-22) — CSV-экспорт движений /api/export/movements.csv + кнопка Export CSV; pytest 70/0 (merged 11c7adf)
- ✅ P13 (2026-10-22) — OpenRouter 429 → cooldown 5 мин + лог, повторные GET без retry-storm; pytest 72/0 (merged 6aac90f)
- ✅ P14 (2026-10-22) — график Stock dynamics (30 days) на recharts 3.10.1 + /api/movements/daily; pytest 76/0 (merged c45b070)
- ✅ P15 (2026-10-23) — Dashboard tabs UI: 4 таба (Forecast, Recommendations, Stock dynamics, Recent movements) с ленивой загрузкой, честные тексты, ARIA-доступность; pytest 78/0, ruff 0, pnpm build OK (feat/dashboard-tabs, ac5e8ba)
- ✅ P16 (2026-10-23) — Low stock таб + UI polish: 5 табов, бейдж количества, дедуп-h3, фикс запятой, empty-state Dynamics, порядок alerts quantity ASC (pytest 78/0; merged 1616e9e)
- ✅ P17 (2026-10-23) — UI polish v2: без theme-toggle, пагинация 15, большой информативный Stock dynamics (600px, сводка, 30/90 дней, легенда); merged de19e50
- ✅ P18 (2026-10-24) — дедуп товаров: миграция 003 + UNIQUE(brand_id, lower(name)) + API 400 при дубле; live 2008→1004, low_stock 98→49 (merged 5800a00)
- ✅ P19 (2026-10-24) — Low stock: /api/low-stock с limit/offset + Reorder point в табе; pytest 84/0 (merged af21660)
- ✅ P20 (2026-10-24) — Products UX: low_stock_only-фильтр, кликабельные сортируемые заголовки, страница 15; live 101 позиция ниже rp (merged 8ed9c03)
- ✅ P21 (2026-10-24) — Forecast: reorder_point/lead_time_days в строках + колонки и AI-бейдж в UI (merged 493830e)
- ✅ P22 (2026-10-24) — vitest: 4 теста DashboardPage (табы/ленивость/пейджер/колонки), фронт-сьют 12/12 (merged d4fd531)
- ✅ P23 (2026-10-24) — скроллбар-степпер убран (flex-wrap в двух навигациях), Brands→Products в хедере, Dynamics v2: Flow+Top movers+Daily detail, KPI-расширение; pytest 88/0, vitest 12/12 (merged 1690ca0)
- ✅ P24 (2026-10-24) — демо-данные: 7787 движений за 30 дней (профили спроса), rp/lt рандомизированы (5–30 / 3–14); merged 941c049
- ✅ P25 (2026-10-24) — Orders: полный цикл закупки (ordered→received/cancelled), приёмка двигает сток+движение+кэш; UI: 6-й таб, Order-кнопки в рекомендациях и low-stock; pytest 95/0 (merged 2e05842)
- ✅ LIVE SMOKE P10–P14 (2026-10-22 19:45, lead, task-6): rebuild после падения демона (docker desktop start); /api/ready 200; миграция 002 в контейнерной БД (reorder_point=10/lead_time_days=7); /api/products — оба поля в items; forecast ×2 байт-идентичны за 0.0s, в логах ровно один openrouter: refining (модель openrouter/free) → «failed: response was not a JSON array — regression fallback» (free-pool лотерея, регрессия сохранена) — P11-кэш-хит доказан; /api/movements/daily 200 (29 items); /api/export/movements.csv 200 text/csv attachment (33 строки); все 6 UI-строк в бандле (Reorder point, Lead time (days), Export CSV, Stock dynamics (30 days), Units in/out); smoke-юзер удалён; finding F1 задокументирован в Risks
