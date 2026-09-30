# GEMINI.md - Alberto POS (Alberto Grocers)

> **This file intentionally contains no rules.**
>
> It used to be a full copy of `AGENTS.md`, which guaranteed the two would drift apart -
> that is exactly how stale `richland_inventory/` paths and an outdated dev-server section
> survived the rebrand and caused a hard-to-diagnose
> `OperationalError: unable to open database file`.

## Read these instead

1. **`AGENTS.md`** - the single source of truth for multi-agent concurrency rules and the
   shared dev-server policy.
2. **`PROJECT_CONTEXT.md`** - what this project is, its current verified state, everyday
   commands, and known gotchas.

## The short version

- Multiple AI sessions share this machine and this repo. Assume any file may change under you.
- Read before write. Make targeted edits. Never rewrite a file wholesale.
- Only touch what your task requires.
- The dev server is shared: use `.\scripts\server.ps1 start` (idempotent). Never run
  `manage.py runserver` yourself, and never kill the server.
- Never `git reset --hard`, `git checkout .`, `git clean -fd`, or delete `db.sqlite3`.
- Check health any time with `.\scripts\verify.ps1`.

Full detail lives in `AGENTS.md` and `PROJECT_CONTEXT.md`. Keep it that way - do not
duplicate their content back into this file.
