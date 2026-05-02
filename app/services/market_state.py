def classify_market_state(market: dict) -> dict:
    price = market["price"]
    change = market["price_change_percent_24h"]
    high = market["high_24h"]
    low = market["low_24h"]
    quote_volume = market["quote_volume_24h"]

    volatility_percent = round(((high - low) / price) * 100, 2) if price else 0
    trend_strength = round(abs(change), 2)

    liquidity_score = "HIGH"
    if quote_volume < 50_000_000:
        liquidity_score = "LOW"
    elif quote_volume < 250_000_000:
        liquidity_score = "MEDIUM"

    state = "MIXED"
    explanation = "Market has no clear dominant condition right now."

    if quote_volume < 50_000_000:
        state = "LOW_LIQUIDITY"
        explanation = "Trading volume is too low. Price moves may be unreliable."

    elif volatility_percent >= 6:
        state = "HIGH_VOLATILITY"
        explanation = "The price range is wide. Risk of sharp reversals is elevated."

    elif change >= 2:
        state = "TREND_UP"
        explanation = "Price is moving upward with positive 24h momentum."

    elif change <= -2:
        state = "TREND_DOWN"
        explanation = "Price is moving downward with negative 24h momentum."

    elif -1 <= change <= 1:
        state = "SIDEWAYS"
        explanation = "Price is mostly flat. There is no strong directional edge."

    return {
        "state": state,
        "volatility_percent": volatility_percent,
        "trend_strength": trend_strength,
        "liquidity_score": liquidity_score,
        "explanation": explanation
    }
