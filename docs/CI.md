# CI Pipeline Overview

Two GitHub Actions workflows plus Dependabot guard every push and pull request.

## Tests (`.github/workflows/tests.yml`)

Runs on **every push** (all branches) and every pull request.

| Job | What it does |
|-----|--------------|
| `pytest` | Boots a throwaway `postgres:16` service container, installs runtime + dev dependencies, runs `pytest --cov` (all 26 tests, **coverage ~90%**) and uploads `coverage.xml` as the `coverage-report` artifact. |
| `frontend` | `pnpm install --frozen-lockfile`, TypeScript check (`tsc -b`), unit tests (`vitest run`), production build (`vite build`). |
| `docker` | Builds the production image (`docker build .`) and validates `compose.yml` (`docker compose config`). |

## Security (`.github/workflows/security.yml`)

Runs on pushes and PRs to `main`, plus a **weekly scan every Monday 02:00 UTC**.

| Job | What it does | Blocking? |
|-----|--------------|-----------|
| `Ruff (Lint & Format)` | `ruff check .` and `ruff format --check .` — style and formatting gates. | Yes |
| `Mypy (Type Check)` | `mypy main.py database.py` — typed surface of the API layer. | Yes |
| `Bandit (SAST)` | Scans application code (`main.py`, `database.py`) only — tests/scripts are out of scope by policy. Results upload as **SARIF** into the GitHub **Security** tab. | Yes |
| `pip-audit (SCA)` | Audits the declared dependency tree (`requirements.txt`) against the OSV database; report uploaded as the `pip-audit-report` JSON artifact. | No — findings don't fail the pipeline; Dependabot opens upgrade PRs. |

Local equivalents:

```bash
ruff check . && ruff format --check .
mypy main.py database.py
bandit -r main.py database.py
pip-audit -r requirements.txt
```

## Dependabot (`.github/dependabot.yml`)

Weekly checks for `pip` (Python), `npm` (frontend) and `github-actions` (workflow actions). Upgrade PRs go through the same CI as everything else.

## pre-commit (`.pre-commit-config.yaml`)

The same Ruff rules run locally on every commit once installed:

```bash
pip install pre-commit
pre-commit install
```

## Conventions

- **Pins are verified, never guessed**: before adding a version constraint, check it resolves — `pip install --dry-run -r requirements.txt -r requirements-dev.txt`.
- **One task = one branch** (`feat/...`), merged only with green CI.
- The Security tab is fed by SARIF (Bandit); vulnerable-dependency alerts come from GitHub's native dependency graph + Dependabot — no duplicate reporter needed.
