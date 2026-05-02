import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.services.db import get_postgres_connection, get_storage_backend


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
FEEDBACK_DB_PATH = DATA_DIR / "novaq_feedback.db"

FEEDBACK_FIELDS = [
    "name",
    "contact",
    "experience_level",
    "main_use_case",
    "clarity_rating",
    "trust_rating",
    "would_pay",
    "price_preference",
    "liked",
    "confusing",
    "missing_features",
    "general_feedback",
    "user_agent",
]


def is_postgres() -> bool:
    return get_storage_backend() == "postgres"


def placeholder() -> str:
    return "%s" if is_postgres() else "?"


def get_connection():
    init_feedback_db()

    if is_postgres():
        return get_postgres_connection()

    connection = sqlite3.connect(FEEDBACK_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_feedback_db() -> None:
    if is_postgres():
        init_feedback_postgres()
        return

    init_feedback_sqlite()


def init_feedback_sqlite() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(FEEDBACK_DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at_utc TEXT NOT NULL,
                name TEXT,
                contact TEXT,
                experience_level TEXT,
                main_use_case TEXT,
                clarity_rating INTEGER,
                trust_rating INTEGER,
                would_pay TEXT,
                price_preference TEXT,
                liked TEXT,
                confusing TEXT,
                missing_features TEXT,
                general_feedback TEXT,
                user_agent TEXT
            )
            """
        )


def init_feedback_postgres() -> None:
    with get_postgres_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_entries (
                id SERIAL PRIMARY KEY,
                created_at_utc TEXT NOT NULL,
                name TEXT,
                contact TEXT,
                experience_level TEXT,
                main_use_case TEXT,
                clarity_rating INTEGER,
                trust_rating INTEGER,
                would_pay TEXT,
                price_preference TEXT,
                liked TEXT,
                confusing TEXT,
                missing_features TEXT,
                general_feedback TEXT,
                user_agent TEXT
            )
            """
        )


def row_to_dict(row) -> dict:
    if row is None:
        return {}

    return dict(row)


def normalize_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def create_feedback_entry(data: dict) -> dict:
    payload = {field: data.get(field, "") for field in FEEDBACK_FIELDS}
    payload["clarity_rating"] = normalize_int(payload.get("clarity_rating"))
    payload["trust_rating"] = normalize_int(payload.get("trust_rating"))
    payload["created_at_utc"] = datetime.now(timezone.utc).isoformat()

    columns = ["created_at_utc", *FEEDBACK_FIELDS]
    placeholders = ", ".join([placeholder()] * len(columns))

    with get_connection() as connection:
        if is_postgres():
            row = connection.execute(
                f"""
                INSERT INTO feedback_entries ({", ".join(columns)})
                VALUES ({placeholders})
                RETURNING *
                """,
                [payload.get(column) for column in columns],
            ).fetchone()
        else:
            cursor = connection.execute(
                f"""
                INSERT INTO feedback_entries ({", ".join(columns)})
                VALUES ({placeholders})
                """,
                [payload.get(column) for column in columns],
            )
            entry_id = cursor.lastrowid
            connection.commit()
            row = connection.execute(
                "SELECT * FROM feedback_entries WHERE id = ?",
                (entry_id,),
            ).fetchone()

    return row_to_dict(row)


def list_feedback_entries(limit: int = 100) -> dict:
    safe_limit = max(1, min(int(limit or 100), 500))
    marker = placeholder()

    with get_connection() as connection:
        total = connection.execute(
            "SELECT COUNT(*) AS total FROM feedback_entries"
        ).fetchone()["total"]
        rows = connection.execute(
            f"""
            SELECT * FROM feedback_entries
            ORDER BY id DESC
            LIMIT {marker}
            """,
            (safe_limit,),
        ).fetchall()

    return {
        "total": total,
        "entries": [row_to_dict(row) for row in rows],
    }


def get_feedback_summary() -> dict:
    with get_connection() as connection:
        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(AVG(NULLIF(clarity_rating, 0)), 0) AS average_clarity_rating,
                COALESCE(AVG(NULLIF(trust_rating, 0)), 0) AS average_trust_rating,
                SUM(CASE WHEN lower(would_pay) = 'yes' THEN 1 ELSE 0 END) AS would_pay_yes,
                SUM(CASE WHEN lower(would_pay) = 'no' THEN 1 ELSE 0 END) AS would_pay_no,
                SUM(CASE WHEN lower(would_pay) = 'maybe' THEN 1 ELSE 0 END) AS would_pay_maybe
            FROM feedback_entries
            """
        ).fetchone()
        price_rows = connection.execute(
            """
            SELECT price_preference, COUNT(*) AS count
            FROM feedback_entries
            WHERE price_preference IS NOT NULL AND price_preference != ''
            GROUP BY price_preference
            ORDER BY count DESC, price_preference ASC
            LIMIT 10
            """
        ).fetchall()

    return {
        "total": summary["total"] or 0,
        "average_clarity_rating": round(float(summary["average_clarity_rating"] or 0), 2),
        "average_trust_rating": round(float(summary["average_trust_rating"] or 0), 2),
        "would_pay_yes": summary["would_pay_yes"] or 0,
        "would_pay_no": summary["would_pay_no"] or 0,
        "would_pay_maybe": summary["would_pay_maybe"] or 0,
        "top_price_preferences": [row_to_dict(row) for row in price_rows],
    }
