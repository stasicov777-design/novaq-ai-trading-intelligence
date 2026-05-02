def get_position_size(risk_level: str, market_state: str | None = None) -> str:
    if market_state in ["LOW_LIQUIDITY", "HIGH_VOLATILITY"]:
        return "0%"

    if risk_level == "LOW":
        return "1%"
    if risk_level == "MEDIUM":
        return "0.5%"
    if risk_level == "HIGH":
        return "0.25%"

    return "0%"


def liquidity_risk_check(market: dict, market_state: dict | None = None) -> dict | None:
    quote_volume = market["quote_volume_24h"]

    if quote_volume < 50_000_000:
        return {
            "symbol": market["symbol"],
            "action": "WAIT",
            "confidence": 20,
            "expected_return": "0%",
            "risk_level": "HIGH",
            "time_horizon": "1h",
            "position_size": "0%",
            "tier": 1,
            "market_state": market_state,
            "reasoning": "Liquidity is too low. Waiting is safer.",
            "failure_scenario": "Low liquidity can cause sharp fake moves and slippage.",
            "alternative_action": "Choose a more liquid asset like BTCUSDT or ETHUSDT.",
            "disclaimer": "Educational signal only. Not financial advice.",
            "market": market
        }

    return None
