# AGENTS.md - Multi-Agent Concurrency & Project Guidelines
# Project: Alberto Inventory POS (Alberto Grocers)

This repository frequently runs multiple simultaneous AI assistant sessions. All agents MUST strictly follow these rules to avoid collisions, prevent overwriting peer progress, and maximize parallel throughput.

---

## 0. Project Layout (read this first)
> **Read `PROJECT_CONTEXT.md` too** - it states the project goal, current verified state,
> everyday commands, and known gotchas. That is the orientation doc for a new session.

```
alberto_system/            <- the Django project (manage.py lives HERE)
  manage.py                <- all commands: .\venv\Scripts\python.exe alberto_system\manage.py <cmd>
  core/                    <- settings, urls, wsgi/asgi, middleware
  inventory/               <- the main app (models, views, api, migrations)
  templates/  static/  staticfiles/  media/
  db.sqlite3               <- the live database
scripts/server.ps1         <- dev server control (see section 4)
scripts/verify.ps1         <- one-command health check ("is everything green?")
venv/                      <- virtualenv (venv\Scripts\python.exe)
```

> **The old folder name `richland_inventory/` no longer exists.** Any command, path or URL mentioning it is stale. Running `richland_inventory\manage.py` produces a server whose `BASE_DIR` points at a deleted folder, which surfaces as the misleading error `OperationalError: unable to open database file` even though the database is perfectly healthy. If you see that error, check the command you used before touching the database.

---

## 1. Surgical, Non-Destructive File Edits
- **Always read before write**: Inspect the freshest content of any target file before editing. Another concurrent session may have updated it moments ago.
- **Atomic line replacements only**: Never rewrite an entire existing file from scratch when updating code or adding features. Use targeted line/chunk replacements (`replace_file_content` / minimal diffs).
- **Preserve unrelated code**: Never delete, comment out, or reformat functions, imports, or styles written by other sessions unless explicitly instructed.
- **No speculative reformatting**: Do not run whole-project formatters, linters, or re-organize imports in files outside your assigned task scope.

---

## 2. Module & Scope Partitioning ("Stay In Your Lane")
- Modify **only** files strictly necessary to complete your specific prompt/task.
- If working on **POS**, avoid touching inventory models, supplier flows, or export scripts unless directly requested.
- If working on **Inventory/Stock**, avoid touching POS frontend templates or authentication templates.
- If working on **Templates/Styling**, do not alter backend business logic.

---

## 3. SQLite & Migration Concurrency
- **Database Engine**: This project runs on **SQLite** (`alberto_system/db.sqlite3`) for lightweight, low-spec local performance.
- **File Locking**: SQLite locks the whole database during write transactions. Keep management commands and database writes brief.
- **Never wipe/delete `db.sqlite3`**: Do NOT run `flush` or delete `db.sqlite3` unless the human user explicitly instructs you to do so.
- **Migration Names**: Before running `makemigrations`, inspect `inventory/migrations/` to observe existing migration numbers. If two sessions add migrations, ensure migration numbers and dependencies are sequential and do not conflict.

---

## 4. Dev Server: Single Shared Instance (CRITICAL)
The dev server is **shared infrastructure for every session on this machine**. It must stay up continuously, and there must never be more than one of it.

- **ALWAYS use the wrapper script — never call `runserver` yourself:**
  ```powershell
  .\scripts\server.ps1 start     # idempotent: reuses a healthy server, no-op if up
  .\scripts\server.ps1 status    # health check
  .\scripts\server.ps1 stop      # ONLY with explicit human approval
  .\scripts\server.ps1 restart   # ONLY with explicit human approval
  ```
- **`start` is idempotent by design.** If a healthy server is already running it prints `reusing it` and exits 0 without spawning anything. **Every session may call `start` freely** — N sessions calling it still yields exactly one server. Run it whenever you need the app; do not probe the port by hand first.
- **NEVER launch `manage.py runserver` directly**, in the foreground or as a background job. A session-bound job is killed whenever that agent session restarts, which takes the server down for everyone and shows up as `ERR_CONNECTION_REFUSED`. The script launches it **detached** precisely so it outlives any session.
- **NEVER kill the server to "fix" it**, and never kill a server you did not start. It is not yours. Restarting it interrupts every other session. If the port is occupied by something unresponsive, **report it and ask the human** — do not force-kill.
- **Why duplicates are dangerous:** on Windows, multiple sockets can bind port 8000 simultaneously (`SO_REUSEADDR`), so a second `runserver` does not fail loudly — it silently steals requests at random. This produces intermittent, unreproducible errors.
- **The server runs with `--noreload`**, which suits this low-spec box but means **Python code changes require an explicit `restart`**. If you change Python code and the browser still shows old behaviour, that is why — ask the human before restarting, since it affects other sessions.
- **Template edits DO hot-reload — but only because the script arranges it.** Django ≥ 2.0 always wraps template loaders in `cached.Loader`, *even with `DEBUG=True`*, so a plain `runserver` would keep serving stale HTML until restart. `scripts/server.ps1` therefore starts the dev server with `TEMPLATE_CACHE=false`, which bypasses the cache: a `.html` edit shows up on the next browser refresh, no restart needed. If you ever start a server by any other means, you lose that and are back to restarting for template edits. `.\scripts\verify.ps1` warns when a `.py` file is newer than the running server.
- **Health probe:** `http://127.0.0.1:8000/accounts/login/` returns `200` for anonymous users. Any HTTP response (even `500`) proves the server process is alive; a TCP refusal means it is down.
- **Logs:** `%TEMP%\alberto_server\runserver.log` and `runserver.err.log`. Read these before assuming a server problem is a code problem.

---

## 5. Git & Workspace Safety
- **Forbidden destructive commands**:
  - `git reset --hard`
  - `git clean -fd`
  - `git checkout .`
  - `git stash drop`
  Any of these commands can destroy uncommitted work from another concurrent AI session.
- Only stage (`git add`) the exact files modified for your specific task.
- **Other sessions' uncommitted changes are not yours.** `git status` will regularly show files
  you did not touch. Leave them alone — do not revert, do not `git add -A`, do not commit them.
- **Branch safety:** the system is **local-only as of 2026-09-30** — there is no online
  deployment, so pushing **does not deploy anything** and the old "`main` auto-deploys to Beta"
  rule no longer applies. `alberto_system/render.yaml` / `build.sh` / `Dockerfile` are obsolete
  leftovers. Still check `git branch --show-current` and confirm with the human before pushing,
  because the remote may be shared — but the reason is coordination, not deploys.
- **The local database is the only copy of the business data.** There is no cloud backup. Run
  `.\scripts\backup.ps1` after any risky change (migrations, bulk edits) and whenever the human
  asks. Never delete `db.sqlite3`, and never run `flush`.

---

## 6. Verify Before Declaring Done
- **Run `.\scripts\verify.ps1` before reporting any task complete.** It is read-only and safe
  during live development. It checks environment, `manage.py check`, missing migrations,
  unapplied migrations, duplicate/stale server processes, HTTP smoke tests on the key pages,
  and the test suite — then prints `GREENLIGHT` or `NOT GREEN`.
- **Interpret a skip correctly.** `tests_integration.py` targets docker-compose services, so it
  skips on a host. Skips are expected, not failures. A real failure is `FAILED`/`ERROR`, or
  `NOT GREEN`.
- **Do not declare success from a single signal.** A 200 on one page is not proof; run the
  full check.
- **If `verify.ps1` reports a failure you did not cause** (e.g. another session's half-finished
  edit), report it to the human rather than "fixing" it by reverting their work.

---

## 7. Code Quality & Architecture Standards

1. **Zero Root Clutter**: Never create loose test/debug scripts in the root directory. For ad-hoc debugging, run Python one-liners or place temporary files in a temp folder and delete them immediately.
2. **HTML Template Balance Guard**: When modifying any template, verify `<div>` balance (`<div\b` count == `</div>` count). Never nest Bootstrap modals inside other modals or parent containers with `overflow: hidden`.
3. **The Orchestrator Pattern**: Keep parent templates as lightweight orchestrators composed of `{% include %}` tags. Add new UI features as isolated partials. Template files should not exceed 400 lines. Python view modules should not exceed 400 lines.
4. **Financial Integrity**: Always wrap payment, refund, or cancellation mutations in `transaction.atomic()` with `select_for_update()`. Never bypass Django signals when updating customer balances.
5. **Brand Design System Consistency**: Use defined design tokens (`--brand-primary`, `--brand-dark`, etc.) and CSS classes. Never hardcode inline hex colors in templates.
6. **The No-Repeat-Failure Wall**: If a fix doesn't work, do NOT retry the same approach. Check logs for the new error, ask the user for browser console output, or pivot to a different approach. Maximum 2 attempts on the same bug using the same strategy before escalating.
7. **The Business Reality Check**: If a prompt contains backwards logic, creates redundant models, or contradicts real-world grocery operations, alert the user immediately, explain the conflict in plain English, and propose a solution before proceeding.

---

## 8. Project Identity & Default Credentials
- **Brand Name**: **Alberto Grocers** / **Alberto Inventory POS**
- **Default Superuser**: `admin` / `123`
- **Branding Assets**:
  - `alberto_system/static/images/logo.png`: Main logo banner (Cart + Alberto Grocers)
  - `alberto_system/static/images/favicon.png`: Circular AG badge icon
  - `alberto_system/static/images/logo_round.png`: Circular AG badge icon
- **Target Deployment**: Optimized for low-spec PCs (DDR3, 4GB RAM, lightweight local execution).
