import json
from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "novaq_signals.db"


def row_to_dict(row) -> dict:
    if row is None:
        return {}

    return dict(row)


def safe_json_loads(value) -> dict:
    if not value:
        return {}

    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_group_stats(items: list[dict]) -> dict:
    total = len(items)
    wins = sum(1 for item in items if item.get("outcome") == "WIN")
    losses = sum(1 for item in items if item.get("outcome") == "LOSS")
    flat = sum(1 for item in items if item.get("outcome") == "FLAT")

    return_values = [
        _safe_float(item.get("return_percent"))
        for item in items
        if item.get("return_percent") is not None
    ]
    score_values = [
        _safe_float(
            item.get("opportunity_score_value", item.get("opportunity_score"))
        )
        for item in items
        if item.get("opportunity_score_value", item.get("opportunity_score")) is not None
    ]

    if total:
        winrate_percent = round((wins / total) * 100, 2)
    else:
        winrate_percent = 0

    if return_values:
        average_return_percent = round(sum(return_values) / len(return_values), 4)
        best_item = max(items, key=lambda item: _safe_float(item.get("return_percent")))
        worst_item = min(items, key=lambda item: _safe_float(item.get("return_percent")))
        best_return_percent = round(_safe_float(best_item.get("return_percent")), 4)
        worst_return_percent = round(_safe_float(worst_item.get("return_percent")), 4)
        best_symbol = best_item.get("symbol")
        worst_symbol = worst_item.get("symbol")
    else:
        average_return_percent = 0
        best_return_percent = 0
        worst_return_percent = 0
        best_symbol = None
        worst_symbol = None

    average_opportunity_score = (
        round(sum(score_values) / len(score_values), 2)
        if score_values
        else 0
    )

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "winrate_percent": winrate_percent,
        "average_return_percent": average_return_percent,
        "best_return_percent": best_return_percent,
        "worst_return_percent": worst_return_percent,
        "average_opportunity_score": average_opportunity_score,
        "best_symbol": best_symbol,
        "worst_symbol": worst_symbol
    }


def group_by_field(items: list[dict], field: str) -> list[dict]:
    grouped = {}

    for item in items:
        key = item.get(field) or "UNKNOWN"
        grouped.setdefault(key, []).append(item)

    results = [
        {
            "key": key,
            "stats": calculate_group_stats(group_items)
        }
        for key, group_items in grouped.items()
    ]

    return sorted(
        results,
        key=lambda item: item["stats"]["average_return_percent"],
        reverse=True
    )


def get_closed_signals(limit: int = 1000) -> list[dict]:
    safe_limit = max(1, min(int(limit), 5000))

    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT * FROM tracked_signals
                WHERE status = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                ("CLOSED", safe_limit)
            ).fetchall()
    except sqlite3.Error:
        return []

    closed_signals = []

    for row in rows:
        item = row_to_dict(row)
        decision = safe_json_loads(item.get("decision_json"))
        market_state = decision.get("market_state") or {}
        signals = decision.get("signals") or {}
        signal_values = signals.get("signals") or {}

        item["market_state_value"] = market_state.get("state") or "UNKNOWN"
        item["signal_trend"] = signal_values.get("trend") or "UNKNOWN"
        item["signal_rsi"] = signal_values.get("rsi") or "UNKNOWN"
        item["signal_momentum"] = signal_values.get("momentum") or "UNKNOWN"
        item["opportunity_score_value"] = (
            item.get("opportunity_score")
            if item.get("opportunity_score") is not None
            else decision.get("opportunity_score")
        )
        item["quality_label_value"] = (
            item.get("quality_label")
            or decision.get("quality_label")
            or "UNKNOWN"
        )

        closed_signals.append(item)

    return closed_signals


def build_performance_analytics(limit: int = 1000) -> dict:
    closed_signals = get_closed_signals(limit)
    summary = calculate_group_stats(closed_signals)
    insights = []

    if summary["total"] == 0:
        insights.append(
            "No closed paper signals yet. Track and evaluate signals to build analytics."
        )
    if summary["total"] and summary["winrate_percent"] < 40:
        insights.append(
            "Winrate is low. Consider stricter signal filters and lower risk exposure."
        )
    if summary["average_return_percent"] < 0:
        insights.append(
            "Average return is negative. Review weak signal categories before scaling."
        )
    if summary["average_return_percent"] > 0:
        insights.append(
            "Average return is positive in paper tracking, but sample size must be considered."
        )
    if summary["total"] < 20:
        insights.append(
            "Sample size is small. Do not trust performance conclusions yet."
        )

    return {
        "product": "NOVAQ AI",
        "analytics_name": "Paper Signal Performance Analytics",
        "summary": summary,
        "by_action": group_by_field(closed_signals, "action"),
        "by_quality_label": group_by_field(closed_signals, "quality_label_value"),
        "by_risk_level": group_by_field(closed_signals, "risk_level"),
        "by_market_state": group_by_field(closed_signals, "market_state_value"),
        "by_signal_trend": group_by_field(closed_signals, "signal_trend"),
        "by_signal_rsi": group_by_field(closed_signals, "signal_rsi"),
        "by_signal_momentum": group_by_field(closed_signals, "signal_momentum"),
        "by_symbol": group_by_field(closed_signals, "symbol"),
        "recent_closed_signals": closed_signals[:25],
        "insights": insights,
        "disclaimer": "Educational analytics only. Not financial advice."
    }
