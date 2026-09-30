# core/__init__.py

# PyMySQL is only needed when using MySQL as the database backend.
# For local development with SQLite, this import is skipped gracefully.
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
