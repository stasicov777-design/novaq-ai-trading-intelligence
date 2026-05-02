from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from fastapi import HTTPException

from app.services.decision_engine import build_decision
from app.services.market_data import fetch_market_data


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "novaq_signals.db"


TRACKING_MIGRATIONS = {
    "close_reason": "TEXT",
    "age_minutes": "REAL",
    "evaluation_json": "TEXT"
}


def get_connection() -> sqlite3.Connection:
    init_tracking_db()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def row_to_dict(row) -> dict:
    if row is None:
        return {}

    return dict(row)


def init_tracking_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tracked_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence INTEGER,
                opportunity_score INTEGER,
                quality_label TEXT,
                expected_return TEXT,
                risk_level TEXT,
                tier INTEGER,
                entry_price REAL,
                entry_time_utc TEXT,
                time_horizon TEXT,
                position_size TEXT,
                status TEXT DEFAULT "OPEN",
                exit_price REAL,
                exit_time_utc TEXT,
                return_percent REAL,
                outcome TEXT,
                decision_json TEXT
            )
            """
        )

        columns = connection.execute(
            "PRAGMA table_info(tracked_signals)"
        ).fetchall()
        existing_columns = {column[1] for column in columns}

        for column_name, column_type in TRACKING_MIGRATIONS.items():
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE tracked_signals ADD COLUMN {column_name} {column_type}"
                )

        connection.commit()


def calculate_paper_return(
    action: str,
    entry_price: float,
    current_price: float
) -> float:
    if entry_price <= 0:
        return 0

    if action in ["BUY", "LONG", "HOLD"]:
        return ((current_price - entry_price) / entry_price) * 100
    if action in ["SELL", "SHORT"]:
        return ((entry_price - current_price) / entry_price) * 100
    if action == "WAIT":
        return 0

    return 0


def calculate_outcome(return_percent: float) -> str:
    if return_percent > 0.1:
        return "WIN"
    if return_percent < -0.1:
        return "LOSS"

    return "FLAT"


def calculate_age_minutes(entry_time_utc: str, now_utc: datetime) -> float:
    if not entry_time_utc:
        return 0

    normalized_entry_time = entry_time_utc.replace("Z", "+00:00")
    entry_time = datetime.fromisoformat(normalized_entry_time)

    if entry_time.tzinfo is None:
        entry_time = entry_time.replace(tzinfo=timezone.utc)

    return round((now_utc - entry_time.astimezone(timezone.utc)).total_seconds() / 60, 4)


def track_signal(symbol: str) -> dict:
    decision = build_decision(symbol)
    market = decision.get("market") or {}
    entry_price = market.get("price")

    if entry_price is None:
        raise HTTPException(
            status_code=503,
            detail="Market price is unavailable. Paper signal cannot be tracked."
        )

    entry_time_utc = datetime.now(timezone.utc).isoformat()
    decision_json = json.dumps(decision, ensure_ascii=True)
    tracked_symbol = decision.get("symbol") or symbol.upper()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO tracked_signals (
                symbol,
                action,
                confidence,
                opportunity_score,
                quality_label,
                expected_return,
                risk_level,
                tier,
                entry_price,
                entry_time_utc,
                time_horizon,
                position_size,
                status,
                decision_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tracked_symbol,
                decision.get("action"),
                decision.get("confidence"),
                decision.get("opportunity_score"),
                decision.get("quality_label"),
                decision.get("expected_return"),
                decision.get("risk_level"),
                decision.get("tier"),
                float(entry_price),
                entry_time_utc,
                decision.get("time_horizon"),
                decision.get("position_size"),
                "OPEN",
                decision_json
            )
        )
        signal_id = cursor.lastrowid
        connection.commit()

        row = connection.execute(
            "SELECT * FROM tracked_signals WHERE id = ?",
            (signal_id,)
        ).fetchone()

    return row_to_dict(row)


def list_tracked_signals(status: str | None = None, limit: int = 50) -> dict:
    safe_limit = max(1, min(int(limit), 500))
    query = "SELECT * FROM tracked_signals"
    params = []

    if status:
        clean_status = status.strip().upper()
        if clean_status not in ["OPEN", "CLOSED"]:
            raise HTTPException(
                status_code=400,
                detail="Status must be OPEN or CLOSED."
            )
        query += " WHERE status = ?"
        params.append(clean_status)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(safe_limit)

    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    signals = [row_to_dict(row) for row in rows]

    return {
        "total": len(signals),
        "signals": signals
    }


def close_signal(signal_id: int, close_reason: str = "MANUAL_CLOSE") -> dict:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM tracked_signals WHERE id = ?",
            (signal_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Tracked signal not found.")

        signal = row_to_dict(row)

        if signal.get("status") == "CLOSED":
            return signal

        entry_price = signal.get("entry_price")
        if not entry_price:
            raise HTTPException(
                status_code=503,
                detail="Entry price is unavailable. Paper signal cannot be closed."
            )

        market = fetch_market_data(signal["symbol"])
        exit_price = market.get("price")

        if exit_price is None:
            raise HTTPException(
                status_code=503,
                detail="Current market price is unavailable. Paper signal cannot be closed."
            )

        return_percent = round(
            calculate_paper_return(signal.get("action"), entry_price, exit_price),
            4
        )
        outcome = calculate_outcome(return_percent)
        now_utc = datetime.now(timezone.utc)
        exit_time_utc = now_utc.isoformat()
        age_minutes = calculate_age_minutes(signal.get("entry_time_utc"), now_utc)

        connection.execute(
            """
            UPDATE tracked_signals
            SET
                status = ?,
                exit_price = ?,
                exit_time_utc = ?,
                return_percent = ?,
                outcome = ?,
                close_reason = ?,
                age_minutes = ?
            WHERE id = ?
            """,
            (
                "CLOSED",
                float(exit_price),
                exit_time_utc,
                return_percent,
                outcome,
                close_reason,
                age_minutes,
                signal_id
            )
        )
        connection.commit()

        updated_row = connection.execute(
            "SELECT * FROM tracked_signals WHERE id = ?",
            (signal_id,)
        ).fetchone()

    return row_to_dict(updated_row)


def evaluate_open_signals(
    take_profit_percent: float = 1.0,
    stop_loss_percent: float = -0.7,
    max_age_minutes: int = 60,
    limit: int = 100
) -> dict:
    safe_limit = max(1, min(int(limit), 500))
    now_utc = datetime.now(timezone.utc)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM tracked_signals
            WHERE status = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            ("OPEN", safe_limit)
        ).fetchall()

    results = []
    closed_count = 0
    still_open_count = 0
    error_count = 0

    for row in rows:
        signal = row_to_dict(row)
        signal_id = signal.get("id")
        symbol = signal.get("symbol")

        try:
            entry_price = signal.get("entry_price")
            if not entry_price:
                raise ValueError("Entry price is unavailable.")

            market = fetch_market_data(symbol)
            current_price = market.get("price")
            if current_price is None:
                raise ValueError("Current market price is unavailable.")

            current_return_percent = round(
                calculate_paper_return(
                    signal.get("action"),
                    float(entry_price),
                    float(current_price)
                ),
                4
            )
            age_minutes = calculate_age_minutes(
                signal.get("entry_time_utc"),
                now_utc
            )

            close_reason = None
            if current_return_percent >= take_profit_percent:
                close_reason = "TAKE_PROFIT"
            elif current_return_percent <= stop_loss_percent:
                close_reason = "STOP_LOSS"
            elif age_minutes >= max_age_minutes:
                close_reason = "MAX_AGE"

            if close_reason:
                exit_time_utc = now_utc.isoformat()
                outcome = calculate_outcome(current_return_percent)
                evaluation_json = json.dumps(
                    {
                        "take_profit_percent": take_profit_percent,
                        "stop_loss_percent": stop_loss_percent,
                        "max_age_minutes": max_age_minutes,
                        "current_return_percent": current_return_percent
                    },
                    ensure_ascii=True
                )

                with get_connection() as connection:
                    connection.execute(
                        """
                        UPDATE tracked_signals
                        SET
                            status = ?,
                            exit_price = ?,
                            exit_time_utc = ?,
                            return_percent = ?,
                            outcome = ?,
                            close_reason = ?,
                            age_minutes = ?,
                            evaluation_json = ?
                        WHERE id = ?
                        """,
                        (
                            "CLOSED",
                            float(current_price),
                            exit_time_utc,
                            current_return_percent,
                            outcome,
                            close_reason,
                            age_minutes,
                            evaluation_json,
                            signal_id
                        )
                    )
                    connection.commit()
                    updated_row = connection.execute(
                        "SELECT * FROM tracked_signals WHERE id = ?",
                        (signal_id,)
                    ).fetchone()

                result = row_to_dict(updated_row)
                result["current_price"] = float(current_price)
                result["current_return_percent"] = current_return_percent
                results.append(result)
                closed_count += 1
            else:
                results.append(
                    {
                        "id": signal_id,
                        "symbol": symbol,
                        "status": "OPEN",
                        "current_price": float(current_price),
                        "current_return_percent": current_return_percent,
                        "age_minutes": age_minutes,
                        "close_reason": None
                    }
                )
                still_open_count += 1

        except Exception as error:
            results.append(
                {
                    "id": signal_id,
                    "symbol": symbol,
                    "status": "ERROR",
                    "error": str(error)
                }
            )
            error_count += 1

    return {
        "evaluated": len(rows),
        "closed": closed_count,
        "still_open": still_open_count,
        "errors": error_count,
        "settings": {
            "take_profit_percent": take_profit_percent,
            "stop_loss_percent": stop_loss_percent,
            "max_age_minutes": max_age_minutes,
            "limit": limit
        },
        "results": results
    }


def get_tracking_summary() -> dict:
    with get_connection() as connection:
        counts = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) AS open_count,
                SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) AS closed_count,
                SUM(CASE WHEN status = 'CLOSED' AND outcome = 'WIN' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN status = 'CLOSED' AND outcome = 'LOSS' THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN status = 'CLOSED' AND outcome = 'FLAT' THEN 1 ELSE 0 END) AS flat,
                SUM(CASE WHEN status = 'CLOSED' AND close_reason = 'TAKE_PROFIT' THEN 1 ELSE 0 END) AS take_profit_closed,
                SUM(CASE WHEN status = 'CLOSED' AND close_reason = 'STOP_LOSS' THEN 1 ELSE 0 END) AS stop_loss_closed,
                SUM(CASE WHEN status = 'CLOSED' AND close_reason = 'MAX_AGE' THEN 1 ELSE 0 END) AS max_age_closed,
                SUM(CASE WHEN status = 'CLOSED' AND COALESCE(close_reason, 'MANUAL_CLOSE') = 'MANUAL_CLOSE' THEN 1 ELSE 0 END) AS manual_closed
            FROM tracked_signals
            """
        ).fetchone()

        returns = connection.execute(
            """
            SELECT
                AVG(return_percent) AS average_return_percent,
                MAX(return_percent) AS best_return_percent,
                MIN(return_percent) AS worst_return_percent
            FROM tracked_signals
            WHERE status = 'CLOSED' AND return_percent IS NOT NULL
            """
        ).fetchone()

    total = counts["total"] or 0
    open_count = counts["open_count"] or 0
    closed_count = counts["closed_count"] or 0
    wins = counts["wins"] or 0
    losses = counts["losses"] or 0
    flat = counts["flat"] or 0
    take_profit_closed = counts["take_profit_closed"] or 0
    stop_loss_closed = counts["stop_loss_closed"] or 0
    max_age_closed = counts["max_age_closed"] or 0
    manual_closed = counts["manual_closed"] or 0

    if closed_count:
        winrate_percent = round((wins / closed_count) * 100, 2)
        average_return_percent = round(returns["average_return_percent"] or 0, 4)
        best_return_percent = round(returns["best_return_percent"] or 0, 4)
        worst_return_percent = round(returns["worst_return_percent"] or 0, 4)
    else:
        winrate_percent = 0
        average_return_percent = 0
        best_return_percent = 0
        worst_return_percent = 0

    return {
        "total": total,
        "open": open_count,
        "closed": closed_count,
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "winrate_percent": winrate_percent,
        "average_return_percent": average_return_percent,
        "best_return_percent": best_return_percent,
        "worst_return_percent": worst_return_percent,
        "take_profit_closed": take_profit_closed,
        "stop_loss_closed": stop_loss_closed,
        "max_age_closed": max_age_closed,
        "manual_closed": manual_closed
    }
