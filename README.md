# Alberto Inventory POS - Alberto Grocers

A comprehensive inventory and Point of Sale (POS) operations system customized for Alberto Grocers, designed for tracking, audit logging, and fast grocery sales.

## Deployment Environments

This project utilizes dedicated branches and Render hosting tiers for testing and production.

### Alpha Environment (Internal Testing)
*   **Purpose:** Development and internal alpha testing.
*   **Branch:** `staging`
*   **Hosting:** [Render (Free Tier)](https://rl-ios-alpha-web.onrender.com/)

### Beta Environment (External/Client Testing)
*   **Purpose:** External acceptance testing and production preview.
*   **Branch:** `main`
*   **Hosting:** [Render (Paid Tier)](https://rl-ios-beta.onrender.com/)

See the [Deployment and Testing Document](Group#_DeployStage.pdf) for detailed test plans, merge history, and feedback results.


*   **Product & Stock Management:** Detailed tracking of products, categories, and real-time stock levels.
*   **Audit Logging:** Automatic tracking of all product edits and stock movements via `django-simple-history`.
*   **POS System:** Integrated Point of Sale for managing sales, customers, and payments.
*   **Reporting:** Generate PDF reports for inventory snapshots, sales history, and supplier deliveries.
*   **REST API:** Fully documented API using Swagger/OpenAPI for integration.

## Tech Stack

*   **Backend:** Python 3.11+, Django 5.2
*   **Database:** MySQL 8.0 (Local/Docker) / PostgreSQL (Production)
*   **Frontend:** Bootstrap 5, Vanilla JavaScript
*   **DevOps:** Docker, WhiteNoise (Static Files), Render (Deployment)
*   **Security:** `django-ratelimit` (Rate Limiting)

---

## Environment Configuration

The application uses `python-decouple` to manage configurations. You must create a `.env` file in the `richland_inventory/` directory.

### `.env` Setup
Create `richland_inventory/.env` and add the following:

```ini
# Security
SECRET_KEY=your-secret-key-here
DEBUG=True

# Database Configuration (Local/Docker)
DB_NAME=richland_inventory_db
DB_USER=user
DB_PASSWORD=password
DB_HOST=db
DB_PORT=3306

# Allowed Hosts (Comma separated)
ALLOWED_HOSTS=127.0.0.1,localhost
```

*Note: For production (Render), these variables are managed via the Render Dashboard environment settings.*

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
docker-compose exec web python richland_inventory/manage.py makemigrations
docker-compose exec web python richland_inventory/manage.py migrate

# Create an admin account
docker-compose exec web python richland_inventory/manage.py createsuperuser

# (Optional) Seed the database with sample data
docker-compose exec web python richland_inventory/manage.py seed_data
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
*   Python 3.11+
*   MySQL Server (e.g., MySQL Community Server or MariaDB)

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
    pip install -r richland_inventory/requirements.txt
    ```
4.  **Database & Static Files**
    ```bash
    cd richland_inventory
    python manage.py migrate
    python manage.py collectstatic --no-input
    ```
5.  **Run Server**
    ```bash
    python manage.py runserver
    ```

---

## Static Files Troubleshooting (Windows/Docker)
If the Admin CSS/JS fails to load on Windows while using Docker:
1.  Run `docker-compose down -v` to clear volumes.
2.  Manually delete the `richland_inventory/staticfiles` folder on your host machine.
3.  Ensure `DEBUG=True` is set in your `.env`.
4.  Rebuild: `docker-compose up --build`.
