import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
FEEDBACK_SQLITE_PATH = DATA_DIR / "novaq_feedback.db"
TRACKING_SQLITE_PATH = DATA_DIR / "novaq_signals.db"


def get_database_url() -> str | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None

    clean_url = database_url.strip()
    if not clean_url:
        return None

    return clean_url


def is_postgres_enabled() -> bool:
    database_url = get_database_url()
    if not database_url:
        return False

    return database_url.startswith(("postgres://", "postgresql://"))


def normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]

    return url


def get_storage_backend() -> str:
    if is_postgres_enabled():
        return "postgres"

    return "sqlite"


def get_postgres_connection():
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. PostgreSQL storage cannot be used.")

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL storage requires psycopg. Install dependencies from requirements.txt."
        ) from error

    try:
        return psycopg.connect(
            normalize_postgres_url(database_url),
            autocommit=True,
            row_factory=dict_row,
        )
    except Exception as error:
        raise RuntimeError("Could not connect to PostgreSQL using DATABASE_URL.") from error


def check_database_health() -> dict:
    backend = get_storage_backend()
    health = {
        "status": "ok",
        "storage_backend": backend,
        "database_url_configured": get_database_url() is not None,
        "checks": {
            "connection": "error",
            "feedback_entries": "error",
            "tracked_signals": "error",
        },
        "error": None,
    }

    try:
        if backend == "postgres":
            with get_postgres_connection() as connection:
                connection.execute("SELECT 1").fetchone()
                health["checks"]["connection"] = "ok"

                connection.execute("SELECT COUNT(*) FROM feedback_entries").fetchone()
                health["checks"]["feedback_entries"] = "ok"

                connection.execute("SELECT COUNT(*) FROM tracked_signals").fetchone()
                health["checks"]["tracked_signals"] = "ok"
        else:
            with sqlite3.connect(FEEDBACK_SQLITE_PATH) as feedback_connection:
                feedback_connection.execute("SELECT 1").fetchone()
                feedback_connection.execute("SELECT COUNT(*) FROM feedback_entries").fetchone()
                health["checks"]["feedback_entries"] = "ok"

            with sqlite3.connect(TRACKING_SQLITE_PATH) as tracking_connection:
                tracking_connection.execute("SELECT 1").fetchone()
                tracking_connection.execute("SELECT COUNT(*) FROM tracked_signals").fetchone()
                health["checks"]["tracked_signals"] = "ok"

            health["checks"]["connection"] = "ok"
    except Exception as error:
        health["status"] = "error"
        health["error"] = str(error)

    if any(check != "ok" for check in health["checks"].values()):
        health["status"] = "error"

    return health
