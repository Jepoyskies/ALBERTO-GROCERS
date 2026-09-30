# PROJECT CONTEXT - Read This First in Every New Session

> **Purpose of this file:** so that any AI session (or new human) can understand *what this
> project is, what state it is in, and what to do next* within 30 seconds of opening the repo.
> Keep it short and current. If you change something structural, update this file in the same task.

**Last updated:** 2026-09-30
**Status:** green - system verified working, dev server live.

---

## 1. What we are building

**Alberto POS (Alberto Grocers).** A grocery-store inventory and Point-of-Sale
operations system: product/stock tracking, sales, suppliers, audit logging, PDF reporting,
and a documented REST API.

**It runs entirely locally on the shop's own PC** (decided 2026-09-30): one dev server on
`127.0.0.1:8000`, one local SQLite file, no internet dependency and no hosting. See
section 7 for what that means in practice.

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
                        | backup.ps1 (verified DB snapshots)
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

# Back up the database (this is the only copy of the shop's data)
.\scripts\backup.ps1
.\scripts\backup.ps1 -List
.\scripts\backup.ps1 -Restore .\backups\db-20260930-120000.sqlite3

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
| Migrations | none missing, all applied (`0040` POS tax, `0041` historical product) |
| `pytest -q` | **48 passed, 4 skipped** (the 4 skips are Docker-only Selenium/HTTP tests) |
| Login | `POST /accounts/login/` -> POS terminal, no errors |
| Dev server | live on `http://127.0.0.1:8000`, detached |
| `db.sqlite3` | present, git-ignored, untracked |

### Entry routing (changed 2026-09-30)

- `/` and a fresh login both land on the **POS terminal** (`/inventory/pos/`).
  A user with no POS permission is sent to the dashboard instead.
- The dashboard still exists at **`/dashboard/`** (`{% url 'dashboard' %}`).
  New links should use `dashboard`; `home` now means "go to the POS terminal".

### POS terminal

`/inventory/pos/` is a full-height workspace built from
`inventory/templates/inventory/pos.html` plus partials in `inventory/pos/`,
with behaviour in `static/pos/pos.js` and `static/pos/pos.css`. Layout follows
the till layout staff already use (toolbar of actions, order pane left,
catalogue right, Subtotal/Tax/Total, Void/Lock/Repeat). F1-F12 are bound, and
any printable key jumps to the search box so a barcode scanner behaves like a
keyboard. It consumes `static/css/brand-tokens.css` - do not give it a private
palette.

- **VAT is inclusive.** Shelf prices already contain 15% VAT, so the terminal
  shows Subtotal (net) and Tax extracted from the gross the customer actually
  pays (1000.00 -> 869.57 + 130.43). `POS_TAX_RATE` in `core/settings.py` is
  the only place the rate lives, and each `POSSale` stores the rate that was
  applied at the time.
- `HeldSale` = parked orders (Save sale / Transfer). `CashDrawerSession` =
  open and close a shift with an over/short count. Both are audited, never
  hard-deleted.
- Tests: `inventory/tests_pos.py` (VAT split, checkout, parked orders, drawer,
  repeat, markup landmarks, access control).

### In-flight work to be aware of (2026-09-30 ~16:28, since resolved)

Another session was mid-way through a POS discount/tax feature: `inventory/models.py` gained
`possale.discount_amount`, `subtotal_amount`, `tax_amount`, `tax_rate`. **RESOLVED** - they
generated and applied migration `0040`, and `0041` (product image, mine) followed it. The
`NOT GREEN` state that this caused has cleared. This note is kept only as a reminder of the
pattern: if `verify.ps1` reports `model changes without a migration`, that is another
session's work in progress - report it, never "fix" it by reverting their models.

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

## 7. Deployment topology - LOCAL ONLY (changed 2026-09-30)

**There is no online deployment. The decision was made by the human on 2026-09-30: this system
runs purely on the shop's own PC with a local SQLite database. No Render, no cloud, no
external services of any kind.**

Consequences that matter:

| Thing | Status |
|---|---|
| `main` / `staging` branches | Kept for history only. **Pushing does not deploy anything.** |
| `alberto_system/render.yaml`, `build.sh`, `Dockerfile` | Obsolete leftovers. Harmless, ignored by the local workflow. |
| Cloudinary (product images) | **Removed from the model** (see gotcha 5). `CLOUDINARY_*` keys must stay EMPTY. |
| `DATABASE_URL` / PostgreSQL | Not used. Leave it unset so Django uses SQLite. |
| `DEBUG` | Stays `True`, and now defaults to `True` in `settings.py` so a lost `.env` cannot break local HTTP. |
| `db.sqlite3` | **The only copy of the business data.** Back it up: `.\scripts\backup.ps1`. |

Because nothing is deployed, committing and pushing are far less dangerous than the old
docs claimed. The old warning "pushing to main deploys to Beta" is **no longer true** - but
still confirm with the human before pushing, because the remote may be a shared repo.

## 8. Known gotchas

1. **`--noreload` plus Django's cached template loader means NOTHING reloads on its own.**
   The dev server runs with `--noreload`, and Django >= 2.0 always wraps template loaders in
   `cached.Loader` - **even with `DEBUG=True`** (`django/template/engine.py`). So an edit to
   a `.py` *or* a `.html` file stays invisible until the server restarts. The dev server
   therefore runs with `TEMPLATE_CACHE=false` (set by `scripts/server.ps1`), which turns the
   template cache off so **template edits appear on the next browser refresh**. Python edits
   still need `.\scripts\server.ps1 restart` (ask the human - it affects other sessions).
   If an edit "does nothing", check this first before touching anything else.
2. **`unable to open database file` almost never means a broken DB.** Check the command you
   ran and the path it resolved before touching `db.sqlite3`.
3. **SQLite locks the whole file during writes.** Keep management commands short-lived.
4. **Uncommitted changes by other sessions are not yours to revert or commit.** `git status`
   may show files you did not touch. Leave them alone.
5. **Do not "restore" Cloudinary.** `Product.image` was a `CloudinaryField`, whose *form field*
   silently uploaded to the Cloudinary API. On a local-only machine that fails the moment
   anybody picks a product image - while the UI looks like a normal file input. It is now a
   plain `models.ImageField(upload_to='product_images/')` (migration `0041`). The `cloudinary`
   and `cloudinary_storage` apps **must stay in `INSTALLED_APPS`**: older migrations
   deconstruct the field as `cloudinary.models.CloudinaryField`, so removing the app would
   break `migrate` on a fresh database.
6. **The whole project lives inside OneDrive.** That is a sync folder, so `db.sqlite3` and
   `backups/` are being synced by OneDrive whether we want it or not. Two consequences:
   SQLite can be corrupted by a sync mid-write, and the "local only" data is in fact leaving
   the machine. If that matters, move the project out of OneDrive and keep backups on an
   unsynced drive. Nothing in the code depends on the current path.
7. **Backups are now load-bearing.** There is no cloud copy. `.\scripts\backup.ps1` takes a
   verified snapshot (SQLite online-backup API + `PRAGMA integrity_check`) and prunes old
   ones; `-List` and `-Restore` are there for the bad day. `verify.ps1` warns if the newest
   backup is over a week old.

## 9. Where we go from here

Nothing is blocked. Pick the next real feature or fix and start on it. When you finish a
substantive change: re-run `.\scripts\verify.ps1`, and update this file if you changed
anything structural.
