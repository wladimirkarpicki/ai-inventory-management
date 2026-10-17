# Migration: Flask → FastAPI + React SPA (shadcn/ui)

Branch: feature/ui-redesign
Status: Design complete; implementation blocked by unstable pwsh/read tools in this session.

## 1. Backend (FastAPI)
Create api/app.py (or replace app.py) with FastAPI:
- /api/auth/login (POST) → JSON {token, user}
- /api/auth/setup (POST) → create admin
- /api/auth/logout (POST) → clear cookie/session
- /api/users (GET/POST) → list / create users (admin only)
- /api/users/{id} (GET/PUT/DELETE) → edit / delete
- /api/brands (GET/POST)
- /api/brands/{id} (GET/PUT/DELETE)
- /api/products (GET/POST with search/sort/pagination)
- /api/products/{id} (GET/PUT/DELETE)
- /api/dashboard/stats (GET)
- /api/export/products-csv (GET)

Keep PostgreSQL via psycopg (FastAPI can use same DB connection per request via dependency injection).

CSRF is no longer needed for JSON API when using JWT/token auth; replace session-csrf with token-based auth (simpler for SPA).
Rate limiting → FastAPI middleware or dependency using in-memory dict (same logic).
Ghost-session → guard checks user exists on each request.

## 2. Frontend (React + shadcn/ui)
Directory: frontend/
- Vite + React + TypeScript
- Tailwind CSS v4 + shadcn/ui init
- Components needed: Button, Card, Input, Label, Table, Badge, DropdownMenu, Dialog, Separator, Sidebar, NavigationMenu
- Router: react-router-dom
- State: React Context or Zustand for auth token + user role
- Each page consumes /api/* endpoints and renders shadcn-styled cards

## 3. Next steps (when tools recover)
- Install pnpm + shadcn CLI
- Run: pnpm dlx shadcn@latest init
- Create components/ui/ with shadcn recipes
- Write api/app.py (FastAPI)
- Update requirements.txt (fastapi, uvicorn)
