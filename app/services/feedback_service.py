import os
import sqlite3
from datetime import datetime, timezone


FEEDBACK_DB_PATH = os.path.join("data", "novaq_feedback.db")

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


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(FEEDBACK_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_feedback_db() -> None:
    os.makedirs("data", exist_ok=True)

    with get_connection() as connection:
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


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def normalize_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def create_feedback_entry(data: dict) -> dict:
    init_feedback_db()

    payload = {field: data.get(field, "") for field in FEEDBACK_FIELDS}
    payload["clarity_rating"] = normalize_int(payload.get("clarity_rating"))
    payload["trust_rating"] = normalize_int(payload.get("trust_rating"))
    payload["created_at_utc"] = datetime.now(timezone.utc).isoformat()

    columns = ["created_at_utc", *FEEDBACK_FIELDS]
    placeholders = ", ".join(["?"] * len(columns))

    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            INSERT INTO feedback_entries ({", ".join(columns)})
            VALUES ({placeholders})
            """,
            [payload.get(column) for column in columns],
        )
        entry_id = cursor.lastrowid
        row = connection.execute(
            "SELECT * FROM feedback_entries WHERE id = ?",
            (entry_id,),
        ).fetchone()

    return row_to_dict(row)


def list_feedback_entries(limit: int = 100) -> dict:
    init_feedback_db()
    safe_limit = max(1, min(int(limit or 100), 500))

    with get_connection() as connection:
        total = connection.execute(
            "SELECT COUNT(*) AS total FROM feedback_entries"
        ).fetchone()["total"]
        rows = connection.execute(
            """
            SELECT * FROM feedback_entries
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return {
        "total": total,
        "entries": [row_to_dict(row) for row in rows],
    }


def get_feedback_summary() -> dict:
    init_feedback_db()

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
        "average_clarity_rating": round(summary["average_clarity_rating"] or 0, 2),
        "average_trust_rating": round(summary["average_trust_rating"] or 0, 2),
        "would_pay_yes": summary["would_pay_yes"] or 0,
        "would_pay_no": summary["would_pay_no"] or 0,
        "would_pay_maybe": summary["would_pay_maybe"] or 0,
        "top_price_preferences": [row_to_dict(row) for row in price_rows],
    }
