# GEMINI.md - Multi-Agent Concurrency & Project Guidelines
# Project: Alberto Inventory POS (Alberto Grocers)

This repository frequently runs multiple simultaneous AI assistant sessions. All agents MUST strictly follow these rules to avoid collisions, prevent overwriting peer progress, and maximize parallel throughput.

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
- **Database Engine**: This project runs on **SQLite** (`richland_inventory/db.sqlite3`) for lightweight, low-spec local performance.
- **File Locking**: SQLite locks the whole database during write transactions. Keep management commands and database writes brief.
- **Never wipe/delete `db.sqlite3`**: Do NOT run `flush` or delete `db.sqlite3` unless the human user explicitly instructs you to do so.
- **Migration Names**: Before running `makemigrations`, inspect `inventory/migrations/` to observe existing migration numbers. If two sessions add migrations, ensure migration numbers and dependencies are sequential and do not conflict.

---

## 4. Port & Background Process Etiquette
- **Dev Server**: The Django server runs on `http://127.0.0.1:8000`.
- **Do not blindly launch duplicate servers**: Before running `runserver`, check if port 8000 or a background task is already serving the application.
- **Do not terminate running servers** unless explicitly asked or required to reload non-reloading configuration.

---

## 5. Git & Workspace Safety
- **Forbidden destructive commands**:
  - `git reset --hard`
  - `git clean -fd`
  - `git checkout .`
  - `git stash drop`
  Any of these commands can destroy uncommitted work from another concurrent AI session.
- Only stage (`git add`) the exact files modified for your specific task.

---

## 6. Project Identity & Default Credentials
- **Brand Name**: **Alberto Grocers** / **Alberto Inventory POS**
- **Default Superuser**: `admin` / `123`
- **Branding Assets**:
  - `richland_inventory/static/images/logo.png`: Main logo banner (Cart + Alberto Grocers)
  - `richland_inventory/static/images/favicon.png`: Circular AG badge icon
  - `richland_inventory/static/images/logo_round.png`: Circular AG badge icon
- **Target Deployment**: Optimized for low-spec PCs (DDR3, 4GB RAM, lightweight local execution).
