def clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return int(max(minimum, min(maximum, round(value))))


def parse_percent(value) -> float:
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    try:
        clean_value = str(value).replace("%", "").strip()
        return float(clean_value)
    except (TypeError, ValueError):
        return 0.0


def calculate_opportunity_score(decision: dict) -> dict:
    action = decision.get("action")
    confidence = decision.get("confidence", 0)
    tier = decision.get("tier", 1)
    risk_level = decision.get("risk_level", "EXTREME")
    expected_return = parse_percent(decision.get("expected_return", "0%"))
    market_state = decision.get("market_state", {})
    state = market_state.get("state")
    signals = decision.get("signals", {})
    signal_values = signals.get("signals", {})
    trend = signal_values.get("trend")
    rsi = signal_values.get("rsi")
    momentum = signal_values.get("momentum")
    risk_reward_ratio = decision.get("risk_reward_ratio")

    try:
        risk_reward_value = (
            float(risk_reward_ratio)
            if risk_reward_ratio is not None
            else None
        )
    except (TypeError, ValueError):
        risk_reward_value = None

    score = confidence * 0.45 + tier * 8

    if action == "BUY":
        score += 10
    elif action == "SELL":
        score += 8
    elif action == "HOLD":
        score += 2
    elif action == "WAIT":
        score -= 12

    if risk_level == "LOW":
        score += 12
    elif risk_level == "MEDIUM":
        score += 6
    elif risk_level == "HIGH":
        score -= 8
    elif risk_level == "EXTREME":
        score -= 25

    if state == "LOW_LIQUIDITY":
        score -= 30
    elif state == "HIGH_VOLATILITY":
        score -= 25
    elif state == "TREND_UP":
        score += 6
    elif state == "TREND_DOWN":
        score += 4
    elif state == "SIDEWAYS":
        score -= 4
    elif state == "MIXED":
        score -= 2

    if action == "BUY" and trend == "BULLISH":
        score += 10
    if action == "SELL" and trend == "BEARISH":
        score += 10
    if action == "BUY" and rsi == "OVERBOUGHT":
        score -= 25
    if action == "SELL" and rsi == "OVERSOLD":
        score -= 20
    if rsi == "OVERSOLD" and action in ["BUY", "HOLD"]:
        score += 5
    if momentum == "POSITIVE" and action == "BUY":
        score += 6
    if momentum == "NEGATIVE" and action == "SELL":
        score += 6
    if momentum == "FLAT":
        score -= 3

    if expected_return >= 2:
        score += 8
    elif expected_return >= 1:
        score += 5
    elif expected_return < 0.2:
        score -= 4

    if risk_reward_value is not None:
        if risk_reward_value >= 2:
            score += 8
        elif risk_reward_value >= 1.5:
            score += 5
        elif risk_reward_value < 1:
            score -= 10

    if "error" in decision:
        score = min(score, 10)
    if action == "WAIT":
        score = min(score, 45)
    if risk_level == "EXTREME":
        score = min(score, 20)
    if state in ["LOW_LIQUIDITY", "HIGH_VOLATILITY"]:
        score = min(score, 35)

    opportunity_score = clamp(score)

    if opportunity_score >= 80:
        quality_label = "TOP"
    elif opportunity_score >= 65:
        quality_label = "STRONG"
    elif opportunity_score >= 45:
        quality_label = "NORMAL"
    else:
        quality_label = "WEAK"

    context = [
        f"action is {action}",
        f"{confidence}% confidence",
        f"{risk_level} risk",
        f"{state or 'UNKNOWN'} market state"
    ]

    if trend:
        context.append(f"{trend} trend")
    if rsi:
        context.append(f"{rsi} RSI")
    if momentum:
        context.append(f"{momentum} momentum")

    risk_reward_note = ""
    if risk_reward_value is not None:
        risk_reward_note = f" Risk/reward is approximately {risk_reward_value:g}."

    why_ranked = (
        f"Ranked as {quality_label} because "
        + ", ".join(context)
        + "."
        + risk_reward_note
    )

    return {
        "opportunity_score": opportunity_score,
        "quality_label": quality_label,
        "why_ranked": why_ranked
    }
