from typing import Any, Literal
from pydantic import BaseModel


class MarketData(BaseModel):
    source: str
    symbol: str
    price: float
    price_change_percent_24h: float
    high_24h: float
    low_24h: float
    volume_24h: float
    quote_volume_24h: float
    time_utc: str


class DecisionResponse(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL", "LONG", "SHORT", "HOLD", "WAIT", "ARBITRAGE"]
    confidence: int
    expected_return: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "EXTREME"]
    time_horizon: str
    position_size: str
    tier: int
    market_state: dict[str, Any]
    signals: dict[str, Any]
    opportunity_score: int
    quality_label: Literal["WEAK", "NORMAL", "STRONG", "TOP"]
    why_ranked: str
    reasoning: str
    failure_scenario: str
    alternative_action: str
    disclaimer: str
    market: dict[str, Any]
