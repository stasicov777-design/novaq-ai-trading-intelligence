from app.services.market_data import fetch_market_data
from app.services.market_state import classify_market_state
from app.services.opportunity_score import calculate_opportunity_score
from app.services.risk_engine import get_position_size, liquidity_risk_check
from app.services.signal_engine import build_signals
from app.services.trade_levels import build_trade_levels


def build_decision(symbol: str) -> dict:
    market = fetch_market_data(symbol)
    market_state = classify_market_state(market)
    state = market_state["state"]
    signals = build_signals(symbol, "1h")

    liquidity_decision = liquidity_risk_check(market, market_state)
    if liquidity_decision:
        liquidity_decision["signals"] = signals
        liquidity_decision.update(build_trade_levels(
            action=liquidity_decision["action"],
            market=market,
            market_state=market_state,
            signals=signals,
            interval="1h"
        ))
        liquidity_decision.update(calculate_opportunity_score(liquidity_decision))
        return liquidity_decision

    change = market["price_change_percent_24h"]

    action = "HOLD"
    confidence = 50
    risk_level = "MEDIUM"
    tier = 2
    reasoning = "Market movement is not strong enough for a high-quality decision."
    failure_scenario = "Price may reverse or stay flat because the signal is weak."
    alternative_action = "WAIT"

    if state == "HIGH_VOLATILITY":
        action = "WAIT"
        confidence = 65
        risk_level = "HIGH"
        tier = 2
        reasoning = "Market volatility is too high. Waiting reduces the chance of entering during a fake move."
        failure_scenario = "A sudden wick or reversal can quickly invalidate the signal."
        alternative_action = "Wait for volatility to cool down before entering."

    elif state == "TREND_UP" and change >= 3:
        action = "BUY"
        confidence = min(78, 58 + int(change * 4))
        risk_level = "MEDIUM"
        tier = 3
        reasoning = "Market state is TREND_UP and price has strong 24h momentum."
        failure_scenario = "Momentum may be exhausted and price can pull back."
        alternative_action = "WAIT for a pullback before entering."

    elif state == "TREND_DOWN" and change <= -3:
        action = "SELL"
        confidence = min(78, 58 + int(abs(change) * 4))
        risk_level = "HIGH"
        tier = 3
        reasoning = "Market state is TREND_DOWN and price is under strong selling pressure."
        failure_scenario = "A sharp rebound can happen after a strong drop."
        alternative_action = "WAIT until selling pressure slows down."

    elif state == "SIDEWAYS":
        action = "WAIT"
        confidence = 62
        risk_level = "LOW"
        tier = 2
        reasoning = "Market state is SIDEWAYS. There is no strong directional edge right now."
        failure_scenario = "A sudden breakout can happen without warning."
        alternative_action = "Set an alert and wait for stronger confirmation."

    signal_values = signals["signals"]

    if signal_values["rsi"] == "OVERBOUGHT" and action == "BUY":
        action = "WAIT"
        confidence = min(confidence, 65)
        risk_level = "HIGH"
        tier = 2
        reasoning = "RSI is overbought, so a BUY entry is blocked until the market cools down."
        failure_scenario = "Buying into overbought conditions can lead to entering just before a pullback."
        alternative_action = "Wait for RSI to normalize before considering a BUY."
    else:
        if (
            signal_values["rsi"] == "OVERSOLD"
            and state != "HIGH_VOLATILITY"
            and action in ["BUY", "HOLD"]
        ):
            confidence += 5

        if signal_values["trend"] == "BULLISH" and state == "TREND_UP":
            confidence += 5

        if signal_values["trend"] == "BEARISH" and state == "TREND_DOWN":
            confidence += 5

    confidence = min(confidence, 85)
    expected_return_value = round(abs(change) * 0.25, 2)

    decision = {
        "symbol": market["symbol"],
        "action": action,
        "confidence": confidence,
        "expected_return": f"{expected_return_value}%",
        "risk_level": risk_level,
        "time_horizon": "1h",
        "position_size": get_position_size(risk_level, state),
        "tier": tier,
        "market_state": market_state,
        "signals": signals,
        "reasoning": reasoning,
        "failure_scenario": failure_scenario,
        "alternative_action": alternative_action,
        "disclaimer": "Educational signal only. Not financial advice.",
        "market": market
    }

    decision.update(build_trade_levels(
        action=decision["action"],
        market=market,
        market_state=market_state,
        signals=signals,
        interval="1h"
    ))
    decision.update(calculate_opportunity_score(decision))
    return decision
