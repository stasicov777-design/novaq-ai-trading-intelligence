from datetime import datetime, timedelta, timezone

from app.services.candle_data import fetch_candles


def safe_round_price(value: float | None) -> float | None:
    if value is None:
        return None

    try:
        price = float(value)
    except (TypeError, ValueError):
        return None

    if price >= 1000:
        return round(price, 2)
    if price >= 1:
        return round(price, 4)

    return round(price, 8)


def calculate_atr_proxy(candles: list[dict], period: int = 14) -> float | None:
    if len(candles) < period:
        return None

    recent_candles = candles[-period:]
    ranges = [
        float(candle["high"]) - float(candle["low"])
        for candle in recent_candles
    ]

    return sum(ranges) / len(ranges)


def get_recent_structure(candles: list[dict], lookback: int = 20) -> dict:
    if not candles:
        return {
            "recent_high": None,
            "recent_low": None,
            "last_close": None,
            "atr_proxy": None,
            "lookback": lookback
        }

    recent_candles = candles[-lookback:]

    return {
        "recent_high": max(float(candle["high"]) for candle in recent_candles),
        "recent_low": min(float(candle["low"]) for candle in recent_candles),
        "last_close": float(candles[-1]["close"]),
        "atr_proxy": calculate_atr_proxy(candles),
        "lookback": lookback
    }


def _valid_until(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _unavailable_levels(market: dict, interval: str) -> dict:
    return {
        "entry_reference_price": safe_round_price(market.get("price")),
        "invalidation_level": None,
        "invalidation_reason": "Trade levels are unavailable because candle data could not be loaded.",
        "stop_zone": None,
        "take_profit_zone": None,
        "risk_reward_ratio": None,
        "decision_valid_until": _valid_until(30),
        "level_type": "DATA_UNAVAILABLE",
        "level_source": "unavailable",
        "level_timeframe": interval
    }


def build_trade_levels(
    action: str,
    market: dict,
    market_state: dict | None = None,
    signals: dict | None = None,
    interval: str = "1h"
) -> dict:
    del market_state, signals

    entry_price = market.get("price")
    symbol = market.get("symbol")

    try:
        entry_price = float(entry_price)
    except (TypeError, ValueError):
        return _unavailable_levels(market, interval)

    if not symbol or entry_price <= 0:
        return _unavailable_levels(market, interval)

    try:
        candles = fetch_candles(symbol, interval="1h", limit=100)
        structure = get_recent_structure(candles)
    except Exception:
        return _unavailable_levels(market, interval)

    recent_high = structure["recent_high"]
    recent_low = structure["recent_low"]
    atr_proxy = structure["atr_proxy"]

    if recent_high is None or recent_low is None:
        return _unavailable_levels(market, interval)

    if atr_proxy is not None:
        buffer = max(entry_price * 0.0015, atr_proxy * 0.25)
    else:
        buffer = entry_price * 0.002

    normalized_action = (action or "WAIT").upper()
    is_long = normalized_action in ["BUY", "LONG"]
    is_short = normalized_action in ["SELL", "SHORT"]

    if is_long:
        invalidation_level = recent_low - buffer
        risk_per_unit = entry_price - invalidation_level

        return {
            "entry_reference_price": safe_round_price(entry_price),
            "invalidation_level": safe_round_price(invalidation_level),
            "invalidation_reason": "Bullish idea is invalidated if price breaks below the recent support zone.",
            "stop_zone": {
                "low": safe_round_price(invalidation_level),
                "high": safe_round_price(recent_low)
            },
            "take_profit_zone": {
                "target_1": safe_round_price(entry_price + risk_per_unit * 1.5),
                "target_2": safe_round_price(entry_price + risk_per_unit * 2.0)
            },
            "risk_reward_ratio": 1.5,
            "decision_valid_until": _valid_until(60),
            "level_type": "LONG_RISK_ZONE",
            "level_source": "recent_candles",
            "level_timeframe": interval
        }

    if is_short:
        invalidation_level = recent_high + buffer
        risk_per_unit = invalidation_level - entry_price

        return {
            "entry_reference_price": safe_round_price(entry_price),
            "invalidation_level": safe_round_price(invalidation_level),
            "invalidation_reason": "Bearish idea is invalidated if price breaks above the recent resistance zone.",
            "stop_zone": {
                "low": safe_round_price(recent_high),
                "high": safe_round_price(invalidation_level)
            },
            "take_profit_zone": {
                "target_1": safe_round_price(entry_price - risk_per_unit * 1.5),
                "target_2": safe_round_price(entry_price - risk_per_unit * 2.0)
            },
            "risk_reward_ratio": 1.5,
            "decision_valid_until": _valid_until(60),
            "level_type": "SHORT_RISK_ZONE",
            "level_source": "recent_candles",
            "level_timeframe": interval
        }

    return {
        "entry_reference_price": safe_round_price(entry_price),
        "invalidation_level": None,
        "invalidation_reason": "No active directional trade idea. Waiting for stronger confirmation is safer.",
        "stop_zone": None,
        "take_profit_zone": None,
        "risk_reward_ratio": None,
        "decision_valid_until": _valid_until(30),
        "level_type": "NO_ACTIVE_TRADE",
        "level_source": "recent_candles",
        "level_timeframe": interval
    }
