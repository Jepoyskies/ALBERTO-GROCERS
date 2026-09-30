# PROJECT CONTEXT - Read This First in Every New Session

> **Purpose of this file:** so that any AI session (or new human) can understand *what this
> project is, what state it is in, and what to do next* within 30 seconds of opening the repo.
> Keep it short and current. If you change something structural, update this file in the same task.

**Last updated:** 2026-09-30
**Status:** green - system verified working, dev server live.

---

## 1. What we are building

**Alberto Grocers - Alberto Inventory POS.** A grocery-store inventory and Point-of-Sale
operations system: product/stock tracking, sales, suppliers, audit logging, PDF reporting,
and a documented REST API.

**Target machine is low-spec** (DDR3 / 4GB RAM). This is a hard design constraint, not a
preference: prefer SQLite over a DB server, avoid heavy JS frameworks, avoid polling, and
favour static/simple rendering. Do not introduce heavyweight dependencies without asking.

## 2. Why this file exists

Three problems kept costing us time, and all three are now prevented by rules + scripts:

| Past problem | What caused it | Now prevented by |
|---|---|---|
| `OperationalError: unable to open database file` on login | A server was started from the **deleted** `richland_inventory/` path, so `BASE_DIR` pointed at a missing folder. The DB was fine. | Section 0 of `AGENTS.md`; all commands use `alberto_system/manage.py` |
| `ERR_CONNECTION_REFUSED`, server "died" | Dev server was a **session-bound background job**; it was killed when the agent session restarted. | `scripts/server.ps1` launches it **detached** |
| Two servers silently fighting over port 8000 | Windows `SO_REUSEADDR` lets a second `runserver` bind the same port instead of erroring, so requests get stolen at random. | `scripts/server.ps1 start` is **idempotent** - it reuses a healthy server |
| Docker started MySQL but never used it | `docker-compose.yml` passed `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`, but `settings.py` only ever reads **`DATABASE_URL`** (via `dj_database_url`). The app silently fell back to SQLite inside the container. | Compose now sets `DATABASE_URL`; MySQL is genuinely used |
| `pip install -r requirements.txt` at risk | The file was saved as **UTF-16LE** (not UTF-8) and contained **duplicate pins** for `cloudinary` / `django-cloudinary-storage`. | File is UTF-8, de-duplicated, and verified pip-parseable |
| `pytest` reported 4 errors that were not real defects | `tests_integration.py` *failed* instead of *skipping* when docker-compose services were absent. | It now skips with an explanatory reason |

## 3. Ground rules (read `AGENTS.md` for the full set)

1. **Multiple AI sessions run here at the same time.** Assume any file may change under you.
2. **Read before write.** Never rewrite a file wholesale; make targeted edits.
3. **Stay in your lane.** Only touch what your task requires.
4. **The dev server belongs to everyone.** Do not kill it. Use `scripts/server.ps1`.
5. **Never** `git reset --hard`, `git checkout .`, `git clean -fd`, or delete `db.sqlite3`.

## 4. Layout

```
alberto_system/         Django project
  manage.py             <- every command runs from here
  core/                 settings.py, urls.py, wsgi/asgi, middleware, cache
  inventory/            main app: models, views, api, urls, migrations, management cmds
  templates/ static/ staticfiles/ media/
  db.sqlite3            live database (git-ignored, never delete)
scripts/                server.ps1 (dev server) | verify.ps1 (health check)
venv/                   virtualenv
```

## 5. Everyday commands

Always use the venv interpreter. Always point at `alberto_system/manage.py`.

```powershell
# Server (shared - start is idempotent, safe for every session to run)
.\scripts\server.ps1 start      # or: status | stop | restart
.\scripts\server.ps1 status

# Full health check ("is everything green?")
.\scripts\verify.ps1

# Django management
.\venv\Scripts\python.exe alberto_system\manage.py check
.\venv\Scripts\python.exe alberto_system\manage.py makemigrations
.\venv\Scripts\python.exe alberto_system\manage.py migrate
.\venv\Scripts\python.exe alberto_system\manage.py createsuperuser

# Tests
.\venv\Scripts\python.exe -m pytest -q
```

**Never** `cd` into `alberto_system` and run bare `manage.py` from another working
directory - a wrong `BASE_DIR` is what caused the database error in the first place.

## 6. Current state (verified 2026-09-30)

| Check | Result |
|---|---|
| `manage.py check` | no issues |
| Migrations | none missing, all applied |
| `pytest -q` | **9 passed, 4 skipped** (the 4 skips are Docker-only Selenium/HTTP tests) |
| Login | `POST /accounts/login/` -> `200` at `/`, no errors |
| Dev server | live on `http://127.0.0.1:8000`, detached |
| `db.sqlite3` | present, git-ignored, untracked |

### About the 4 skipped tests
`alberto_system/inventory/tests_integration.py` targets the **docker-compose** services
(`web:8000`, `selenium:4444`). Run on a normal host they **skip** rather than error, which is
correct. To actually run them:

```bash
docker-compose up --build          # start web + selenium
docker-compose run --rm tests pytest -v
```

### Environment
- `alberto_system/.env` exists; `DATABASE_URL` is intentionally unset so Django falls back to
  SQLite. Render/PostgreSQL is used only when `DATABASE_URL` is set.
- Superuser: `admin` / `123`

### Local SQLite vs Docker MySQL (they are intentionally different)
- **Host:** SQLite at `alberto_system/db.sqlite3`. This is the live dev database.
- **Docker:** MySQL, because `docker-compose.yml` sets
  `DATABASE_URL=mysql://user:password@db:3306/alberto_inventory_db`.
- `PyMySQL` is in `requirements.txt` and `core/__init__.py` registers it as `MySQLdb`, so the
  MySQL path is real. If you add a DB env var to compose, it must go into `DATABASE_URL` —
  `settings.py` reads **no** `DB_*` variables.
- `db` and `web` have healthchecks and `tests` waits on `service_healthy`, so `migrate` no
  longer races MySQL startup.

## 7. Deployment topology

- `main` -> Beta (client testing) - https://rl-ios-beta.onrender.com
- `staging` -> Alpha (internal testing) - https://rl-ios-alpha-web.onrender.com
- `feature/*` branches exist on origin for isolated work.

**Check which branch you are on before committing.** Do not push to `main` or `staging`
without explicit human approval - it deploys.

## 8. Known gotchas

1. **The `--noreload` dev server does not hot-reload.** After editing Python code you must
   `.\scripts\server.ps1 restart` (ask the human - it affects other sessions). Templates and
   static files still reload without a restart.
2. **`unable to open database file` almost never means a broken DB.** Check the command you
   ran and the path it resolved before touching `db.sqlite3`.
3. **SQLite locks the whole file during writes.** Keep management commands short-lived.
4. **Uncommitted changes by other sessions are not yours to revert or commit.** `git status`
   may show files you did not touch. Leave them alone.

## 9. Where we go from here

Nothing is blocked. Pick the next real feature or fix and start on it. When you finish a
substantive change: re-run `.\scripts\verify.ps1`, and update this file if you changed
anything structural.
