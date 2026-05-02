from app.services.decision_engine import build_decision


DEFAULT_FEED_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "TONUSDT"
]


def _build_error_item(symbol: str, error: Exception) -> dict:
    return {
        "symbol": symbol,
        "action": "WAIT",
        "confidence": 0,
        "expected_return": "0%",
        "risk_level": "EXTREME",
        "time_horizon": "1h",
        "position_size": "0%",
        "tier": 1,
        "reasoning": "Market data or signal data is unavailable. Waiting is required.",
        "failure_scenario": "Without reliable data, any action would be unsafe.",
        "alternative_action": "WAIT until data providers recover.",
        "disclaimer": "Educational signal only. Not financial advice.",
        "opportunity_score": 0,
        "quality_label": "WEAK",
        "why_ranked": "Ranked as WEAK because market or signal data is unavailable.",
        "error": str(error)
    }


def build_decision_feed(symbols: list[str] | None = None) -> dict:
    selected_symbols = [
        symbol.strip().upper()
        for symbol in symbols
        if symbol and symbol.strip()
    ] if symbols else DEFAULT_FEED_SYMBOLS

    if not selected_symbols:
        selected_symbols = DEFAULT_FEED_SYMBOLS

    results = []

    for symbol in selected_symbols:
        try:
            results.append(build_decision(symbol))
        except Exception as error:
            results.append(_build_error_item(symbol, error))

    results.sort(
        key=lambda item: (
            item.get("opportunity_score", 0),
            item.get("tier", 0),
            item.get("confidence", 0)
        ),
        reverse=True
    )

    summary = {
        "total": len(results),
        "buy": sum(1 for item in results if item.get("action") == "BUY"),
        "sell": sum(1 for item in results if item.get("action") == "SELL"),
        "hold": sum(1 for item in results if item.get("action") == "HOLD"),
        "wait": sum(1 for item in results if item.get("action") == "WAIT"),
        "top_symbol": results[0].get("symbol") if results else None,
        "top_action": results[0].get("action") if results else None,
        "top_score": results[0].get("opportunity_score") if results else None,
        "top_quality": results[0].get("quality_label") if results else None,
        "top_reason": results[0].get("why_ranked") if results else None
    }

    return {
        "product": "NOVAQ AI",
        "feed_name": "What To Do Now Feed",
        "symbols": selected_symbols,
        "summary": summary,
        "results": results,
        "disclaimer": "Educational signal only. Not financial advice."
    }
