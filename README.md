# Alberto Inventory POS - Alberto Grocers

A comprehensive inventory and Point of Sale (POS) operations system customized for Alberto Grocers, designed for tracking, audit logging, and fast grocery sales.

> **Working in this repo with an AI assistant?** Read **`PROJECT_CONTEXT.md`** (goal, current
> state, commands, gotchas) and **`AGENTS.md`** (multi-agent concurrency + shared dev-server
> rules) first. Health check: `.\scripts\verify.ps1`.

## Deployment Environments

**This system is local-only (decided 2026-09-30).** It runs entirely on the shop's own PC:
one Django dev server on `127.0.0.1:8000` and one local SQLite database at
`alberto_system/db.sqlite3`. There is no online deployment, no cloud database, and no
external service of any kind.

*   **Start / stop the app:** `.\scripts\server.ps1 start` (or `stop` / `restart` / `status`).
*   **Health check:** `.\scripts\verify.ps1` — prints `GREENLIGHT` or `NOT GREEN`.
*   **Back up the data:** `.\scripts\backup.ps1` — verified snapshot, `-List`, `-Restore`.
    The local `db.sqlite3` is the *only* copy of the business data, so back it up regularly.
*   **Branches:** `main` and `staging` are kept for history only. Pushing does not deploy.

`alberto_system/render.yaml`, `alberto_system/build.sh` and `Dockerfile` are obsolete
leftovers from the previous hosted setup. They are harmless and no longer part of the
workflow.

See the [Deployment and Testing Document](Group#_DeployStage.pdf) for the historical test
plans, merge history, and feedback results from when the project was hosted online.


*   **Product & Stock Management:** Detailed tracking of products, categories, and real-time stock levels.
*   **Audit Logging:** Automatic tracking of all product edits and stock movements via `django-simple-history`.
*   **POS System:** Integrated Point of Sale for managing sales, customers, and payments.
*   **Reporting:** Generate PDF reports for inventory snapshots, sales history, and supplier deliveries.
*   **REST API:** Fully documented API using Swagger/OpenAPI for integration.

## Tech Stack

*   **Backend:** Python 3.11+, Django 5.2
*   **Database:** SQLite (local, the only database used)
*   **Frontend:** Bootstrap 5, Vanilla JavaScript
*   **Media:** local files under `alberto_system/media/` (product images, expense receipts)
*   **Security:** `django-ratelimit` (Rate Limiting)

---

## Environment Configuration

The application uses `python-decouple` to manage configurations. You must create a `.env` file in the `alberto_system/` directory.

### `.env` Setup
Create `alberto_system/.env` and add the following:

```ini
# Security
SECRET_KEY=your-secret-key-here
DEBUG=True

# Allowed Hosts (Comma separated)
ALLOWED_HOSTS=127.0.0.1,localhost
```

**Database:** leave `DATABASE_URL` **unset**. `core/settings.py` then uses SQLite at
`alberto_system/db.sqlite3`, which needs no server and no configuration. This is the only
database the system uses — there is no PostgreSQL in the local-only setup.

*Note: `DEBUG=True` is correct here and is now also the default in `settings.py`, so a lost
`.env` cannot silently switch on production HTTPS settings and break local access. Leave the
`CLOUDINARY_*` values **empty** — media is stored locally under `alberto_system/media/`.*

---

## Running with Docker (Recommended)

Docker is the easiest way to get the system running with all dependencies and the MySQL database correctly configured.

### 1. Build and Start
This command builds the images and starts the web and database services. It also automatically runs migrations and collects static files.
```bash
docker-compose up --build
```

### 2. Initial Setup
Run these once the containers are healthy:
```bash
# Apply database migrations
docker-compose exec web python alberto_system/manage.py makemigrations
docker-compose exec web python alberto_system/manage.py migrate

# Create an admin account
docker-compose exec web python alberto_system/manage.py createsuperuser

# (Optional) Seed the database with sample data
docker-compose exec web python alberto_system/manage.py seed_data
```

### 3. Access the System
*   **Dashboard:** [http://localhost:8000](http://localhost:8000)
*   **Admin Panel:** [http://localhost:8000/admin](http://localhost:8000/admin)
*   **API Docs:** [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

---

## Testing with Docker

The system includes automated integration tests that verify the HTTP response and browser rendering using Selenium.

### Run Integration Tests
This command starts the database, web app, and a standalone Chrome container to run the test suite:
```bash
docker-compose run --rm tests pytest -v
```

### What's Tested:
*   **HTTP Layer:** Verifies that the homepage and login pages return a `200 OK` status.
*   **Browser Layer (Selenium):** Uses a real Chrome instance to verify that the UI components (like login forms) are rendered correctly.

---

## Database Maintenance

If you need to reset the system data, use these commands within the Render Shell or Docker container:

### 1. Reset Data (Flush & Seed)
This removes all current data and re-populates it using the `seed_data` script.
```bash
# Safely clear all data from the database
python manage.py flush --no-input

# Re-populate with seed data
python manage.py seed_data
```

### 2. Full Database Reset
If you need a complete clean slate, including re-applying migrations:
```bash
# 1. Remove all database tables
python manage.py flush --no-input

# 2. Re-apply migrations
python manage.py migrate

# 3. Re-populate with seed data
python manage.py seed_data
```

### 3. Create Superuser
If you need to create an administrator account:
```bash
python manage.py createsuperuser
```



### Prerequisites
*   Python 3.11+ (Django 5.2)
*   **No database server required locally** — SQLite is used by default

### Installation
1.  **Clone & Navigate**
    ```bash
    git clone <repository-url>
    cd Rich-Land-IOS
    ```
2.  **Virtual Environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # OR
    .\venv\Scripts\activate   # Windows
    ```
3.  **Install Dependencies**
    ```bash
    pip install -r alberto_system/requirements.txt
    ```
4.  **Database & Static Files**
    ```bash
    cd alberto_system
    python manage.py migrate
    python manage.py collectstatic --no-input
    ```
5.  **Run Server**
    From the repository root (note: do **not** `cd` into `alberto_system` first):
    ```powershell
    .\scripts\server.ps1 start
    ```
    This launches the dev server **detached** on `http://127.0.0.1:8000` and is safe to
    re-run — it reuses a healthy server instead of starting a duplicate.
    Check it any time with `.\scripts\server.ps1 status`, or run a full health check with
    `.\scripts\verify.ps1`. See `AGENTS.md` section 4 for the shared-server rules.

---

## Static Files Troubleshooting (Windows/Docker)
If the Admin CSS/JS fails to load on Windows while using Docker:
1.  Run `docker-compose down -v` to clear volumes.
2.  Manually delete the `alberto_system/staticfiles` folder on your host machine.
3.  Ensure `DEBUG=True` is set in your `.env`.
4.  Rebuild: `docker-compose up --build`.
