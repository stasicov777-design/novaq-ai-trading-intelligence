from fastapi import HTTPException

from app.services.candle_data import fetch_candles
from app.services.market_data import normalize_symbol


def calculate_sma(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None

    return round(sum(values[-period:]) / period, 4)


def calculate_ema(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None

    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period

    for value in values[period:]:
        ema = (value * multiplier) + (ema * (1 - multiplier))

    return round(ema, 4)


def calculate_rsi(values: list[float], period: int = 14) -> float | None:
    if period <= 0 or len(values) < period + 1:
        return None

    changes = [
        values[index] - values[index - 1]
        for index in range(1, len(values))
    ]
    recent_changes = changes[-period:]

    average_gain = sum(max(change, 0) for change in recent_changes) / period
    average_loss = sum(abs(min(change, 0)) for change in recent_changes) / period

    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0

    relative_strength = average_gain / average_loss
    return round(100 - (100 / (1 + relative_strength)), 4)


def build_signals(symbol: str, interval: str = "1h") -> dict:
    clean_symbol = normalize_symbol(symbol)
    candles = fetch_candles(clean_symbol, interval, 100)

    if len(candles) < 2:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Not enough candle data to calculate signals. Decision must be WAIT.",
                "symbol": clean_symbol,
                "interval": interval
            }
        )

    close_prices = [candle["close"] for candle in candles]
    sma_20 = calculate_sma(close_prices, 20)
    ema_20 = calculate_ema(close_prices, 20)
    rsi_14 = calculate_rsi(close_prices, 14)
    last_close = close_prices[-1]
    previous_close = close_prices[-2]

    if previous_close == 0:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Cannot calculate momentum from zero previous close. Decision must be WAIT.",
                "symbol": clean_symbol,
                "interval": interval
            }
        )

    momentum_percent = ((last_close - previous_close) / previous_close) * 100

    trend_signal = "NEUTRAL"
    if ema_20 is not None and last_close > ema_20:
        trend_signal = "BULLISH"
    elif ema_20 is not None and last_close < ema_20:
        trend_signal = "BEARISH"

    rsi_signal = "NEUTRAL"
    if rsi_14 is not None and rsi_14 >= 70:
        rsi_signal = "OVERBOUGHT"
    elif rsi_14 is not None and rsi_14 <= 30:
        rsi_signal = "OVERSOLD"

    momentum_signal = "FLAT"
    if momentum_percent > 0.2:
        momentum_signal = "POSITIVE"
    elif momentum_percent < -0.2:
        momentum_signal = "NEGATIVE"

    explanation = (
        f"{interval} signals show {trend_signal.lower()} trend, "
        f"{rsi_signal.lower()} RSI, and {momentum_signal.lower()} momentum."
    )

    return {
        "symbol": clean_symbol,
        "interval": interval,
        "last_close": last_close,
        "sma_20": sma_20,
        "ema_20": ema_20,
        "rsi_14": rsi_14,
        "momentum_percent": round(momentum_percent, 4),
        "signals": {
            "trend": trend_signal,
            "rsi": rsi_signal,
            "momentum": momentum_signal
        },
        "explanation": explanation
    }
