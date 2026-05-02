from datetime import datetime, timezone
from fastapi import HTTPException
import requests


def normalize_symbol(symbol: str) -> str:
    return symbol.upper().replace("-", "").replace("/", "").strip()


def fetch_from_binance(symbol: str) -> dict:
    clean_symbol = normalize_symbol(symbol)

    url = "https://api.binance.com/api/v3/ticker/24hr"
    params = {"symbol": clean_symbol}

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    return {
        "source": "binance",
        "symbol": data["symbol"],
        "price": float(data["lastPrice"]),
        "price_change_percent_24h": float(data["priceChangePercent"]),
        "high_24h": float(data["highPrice"]),
        "low_24h": float(data["lowPrice"]),
        "volume_24h": float(data["volume"]),
        "quote_volume_24h": float(data["quoteVolume"]),
        "time_utc": datetime.now(timezone.utc).isoformat()
    }


def fetch_from_coinbase(symbol: str) -> dict:
    clean_symbol = normalize_symbol(symbol)

    if clean_symbol.endswith("USDT"):
        base = clean_symbol.replace("USDT", "")
    elif clean_symbol.endswith("USD"):
        base = clean_symbol.replace("USD", "")
    else:
        base = clean_symbol

    product_id = f"{base}-USD"
    url = f"https://api.exchange.coinbase.com/products/{product_id}/stats"

    response = requests.get(
        url,
        timeout=10,
        headers={"User-Agent": "NOVAQ-AI/0.5.0"}
    )
    response.raise_for_status()
    data = response.json()

    last_price = float(data["last"])
    open_price = float(data["open"])
    change_percent = ((last_price - open_price) / open_price) * 100 if open_price else 0
    volume = float(data["volume"])

    return {
        "source": "coinbase",
        "symbol": product_id,
        "price": last_price,
        "price_change_percent_24h": round(change_percent, 2),
        "high_24h": float(data["high"]),
        "low_24h": float(data["low"]),
        "volume_24h": volume,
        "quote_volume_24h": round(volume * last_price, 2),
        "time_utc": datetime.now(timezone.utc).isoformat()
    }


def fetch_market_data(symbol: str) -> dict:
    errors = []

    try:
        return fetch_from_binance(symbol)
    except Exception as error:
        errors.append(f"Binance unavailable: {str(error)}")

    try:
        return fetch_from_coinbase(symbol)
    except Exception as error:
        errors.append(f"Coinbase unavailable: {str(error)}")

    raise HTTPException(
        status_code=503,
        detail={
            "message": "All market data providers are unavailable. Decision must be WAIT.",
            "errors": errors
        }
    )
