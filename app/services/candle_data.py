from fastapi import HTTPException
import requests

from app.services.market_data import normalize_symbol


def fetch_binance_candles(
    symbol: str,
    interval: str = "1h",
    limit: int = 100
) -> list[dict]:
    clean_symbol = normalize_symbol(symbol)

    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": clean_symbol,
        "interval": interval,
        "limit": limit
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Candle data provider is unavailable. Decision must be WAIT.",
                "provider": "binance",
                "error": str(error)
            }
        ) from error

    candles = [
        {
            "open_time": int(item[0]),
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
            "close_time": int(item[6])
        }
        for item in data
    ]

    if not candles:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Candle data provider returned no candles. Decision must be WAIT.",
                "provider": "binance",
                "symbol": clean_symbol
            }
        )

    return candles


def fetch_candles(
    symbol: str,
    interval: str = "1h",
    limit: int = 100
) -> list[dict]:
    return fetch_binance_candles(symbol, interval, limit)
