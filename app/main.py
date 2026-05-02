from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.schemas.decision import DecisionResponse, MarketData
from app.services.candle_data import fetch_candles
from app.services.decision_engine import build_decision
from app.services.feed_engine import build_decision_feed
from app.services.market_data import fetch_market_data
from app.services.market_state import classify_market_state
from app.services.performance_analytics import build_performance_analytics
from app.services.signal_engine import build_signals
from app.services.signal_tracking import (
    close_signal,
    evaluate_open_signals,
    get_tracking_summary,
    init_tracking_db,
    list_tracked_signals,
    track_signal,
)
from app.version import APP_NAME, APP_VERSION

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="AI Decision Intelligence Layer for crypto markets"
)


@app.on_event("startup")
def startup_event():
    init_tracking_db()


@app.get("/")
def root():
    return {
        "product": "NOVAQ AI",
        "version": APP_VERSION,
        "status": "online",
        "message": "AI Decision Intelligence Layer is running",
        "dashboard": "http://127.0.0.1:8000/dashboard",
        "feed": "http://127.0.0.1:8000/feed",
        "feed_dashboard": "http://127.0.0.1:8000/feed-dashboard",
        "tracking_summary": "http://127.0.0.1:8000/tracking-summary",
        "tracked_signals": "http://127.0.0.1:8000/tracked-signals",
        "tracking_dashboard": "http://127.0.0.1:8000/tracking-dashboard",
        "evaluate_open_signals": "http://127.0.0.1:8000/evaluate-open-signals",
        "performance_analytics": "http://127.0.0.1:8000/performance-analytics",
        "performance_dashboard": "http://127.0.0.1:8000/performance-dashboard",
        "docs": "http://127.0.0.1:8000/docs",
        "time_utc": datetime.now(timezone.utc).isoformat()
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/market/{symbol}", response_model=MarketData)
def get_market_data(symbol: str):
    return fetch_market_data(symbol)


@app.get("/market-state/{symbol}")
def get_market_state(symbol: str):
    market = fetch_market_data(symbol)
    return classify_market_state(market)


@app.get("/candles/{symbol}")
def get_candles(symbol: str, interval: str = "1h", limit: int = 100):
    return fetch_candles(symbol, interval, limit)


@app.get("/signals/{symbol}")
def get_signals(symbol: str, interval: str = "1h"):
    return build_signals(symbol, interval)


@app.get("/decision/{symbol}", response_model=DecisionResponse)
def get_decision(symbol: str):
    return build_decision(symbol)


@app.get("/feed")
def get_feed(symbols: str | None = None):
    parsed_symbols = None
    if symbols:
        parsed_symbols = [
            item.strip().upper()
            for item in symbols.split(",")
            if item.strip()
        ]
    return build_decision_feed(parsed_symbols)


@app.post("/track/{symbol}")
def create_tracked_signal(symbol: str):
    return track_signal(symbol)


@app.get("/track/{symbol}")
def create_tracked_signal_get(symbol: str):
    return track_signal(symbol)


@app.get("/tracked-signals")
def get_tracked_signals(status: str | None = None, limit: int = 50):
    return list_tracked_signals(status, limit)


@app.post("/tracked-signals/{signal_id}/close")
def close_tracked_signal(signal_id: int, close_reason: str = "MANUAL_CLOSE"):
    return close_signal(signal_id, close_reason)


@app.get("/tracking-summary")
def tracking_summary():
    return get_tracking_summary()


@app.post("/evaluate-open-signals")
def evaluate_open_signals_endpoint(
    take_profit_percent: float = 1.0,
    stop_loss_percent: float = -0.7,
    max_age_minutes: int = 60,
    limit: int = 100
):
    return evaluate_open_signals(
        take_profit_percent=take_profit_percent,
        stop_loss_percent=stop_loss_percent,
        max_age_minutes=max_age_minutes,
        limit=limit
    )


@app.get("/evaluate-open-signals")
def evaluate_open_signals_get(
    take_profit_percent: float = 1.0,
    stop_loss_percent: float = -0.7,
    max_age_minutes: int = 60,
    limit: int = 100
):
    return evaluate_open_signals(
        take_profit_percent=take_profit_percent,
        stop_loss_percent=stop_loss_percent,
        max_age_minutes=max_age_minutes,
        limit=limit
    )


@app.get("/performance-analytics")
def performance_analytics(limit: int = 1000):
    return build_performance_analytics(limit)


@app.get("/performance-dashboard", response_class=HTMLResponse)
def performance_dashboard():
    return """
<!DOCTYPE html>
<html lang="en" translate="no">
<head>
    <meta charset="UTF-8" />
    <title>NOVAQ AI Performance Analytics</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="google" content="notranslate" />

    <style>
        * { box-sizing: border-box; }

        .notranslate {
            unicode-bidi: isolate;
        }

        :root {
            --bg: #070b12;
            --panel: #101722;
            --line: rgba(255, 255, 255, 0.08);
            --text: #f4f7fb;
            --muted: #8d99ae;
            --cyan: #00ffc2;
            --blue: #4b8dff;
            --red: #ff5c7a;
            --amber: #ffd166;
            --green: #62f5a7;
        }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: Inter, Arial, sans-serif;
            color: var(--text);
            background: linear-gradient(180deg, #070b12 0%, #0a101a 52%, #06090f 100%);
        }

        .page {
            width: min(1380px, calc(100% - 40px));
            margin: 0 auto;
            padding: 32px 0 44px;
        }

        .header {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 24px;
            margin-bottom: 22px;
        }

        .logo {
            font-size: 30px;
            font-weight: 900;
            line-height: 1;
        }

        .logo span { color: var(--cyan); }

        .subtitle {
            margin-top: 8px;
            color: var(--muted);
            font-size: 15px;
        }

        .top-nav {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 18px;
        }

        .top-nav a,
        .nav-link {
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            border-radius: 8px;
            padding: 10px 12px;
            text-decoration: none;
            font-size: 12px;
            font-weight: 900;
            white-space: nowrap;
        }

        .top-nav a:hover,
        .nav-link:hover {
            filter: brightness(1.08);
        }

        .toolbar {
            display: grid;
            grid-template-columns: minmax(120px, 220px) auto minmax(0, 1fr);
            gap: 12px;
            align-items: center;
            background: rgba(16, 23, 34, 0.9);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 18px;
        }

        input {
            width: 100%;
            min-width: 0;
            border: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.045);
            color: var(--text);
            padding: 13px 14px;
            border-radius: 8px;
            outline: none;
            font-size: 14px;
            font-weight: 700;
        }

        button {
            border: 0;
            border-radius: 8px;
            padding: 13px 18px;
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            cursor: pointer;
            font-weight: 900;
            white-space: nowrap;
        }

        .status {
            color: var(--cyan);
            font-size: 12px;
            font-weight: 800;
            text-align: right;
        }

        .summary {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 18px;
        }

        .summary-card,
        .panel {
            background: rgba(16, 23, 34, 0.92);
            border: 1px solid var(--line);
            border-radius: 8px;
        }

        .summary-card {
            min-height: 88px;
            padding: 15px;
        }

        .label {
            color: var(--muted);
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
        }

        .summary-value {
            margin-top: 10px;
            font-size: 26px;
            font-weight: 950;
            overflow-wrap: anywhere;
        }

        .panel {
            padding: 16px;
            margin-bottom: 14px;
        }

        .panel-title {
            font-size: 17px;
            font-weight: 950;
            margin-bottom: 12px;
        }

        .insights {
            display: grid;
            gap: 8px;
        }

        .insight {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.035);
            color: #dce5f3;
            padding: 11px 12px;
            line-height: 1.45;
        }

        .groups {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
        }

        .table-wrap {
            overflow: visible;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }

        th,
        td {
            border-bottom: 1px solid var(--line);
            padding: 10px 8px;
            text-align: left;
            font-size: 13px;
            vertical-align: top;
            word-break: break-word;
        }

        th {
            color: var(--muted);
            font-size: 11px;
            text-transform: uppercase;
        }

        td {
            color: #e3eaf5;
        }

        .key {
            font-weight: 900;
            color: var(--text);
        }

        .badge {
            display: inline-block;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 5px 8px;
            background: rgba(255, 255, 255, 0.045);
            color: #e3eaf5;
            font-size: 12px;
            font-weight: 900;
            margin: 1px;
        }

        .group-list {
            display: grid;
            gap: 10px;
        }

        .group-card {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 12px;
            background: rgba(255, 255, 255, 0.035);
        }

        .group-key {
            font-weight: 950;
            margin-bottom: 10px;
            word-break: break-word;
        }

        .group-stats {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 8px;
        }

        .group-stat {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 8px;
            min-width: 0;
        }

        .group-stat strong {
            display: block;
            margin-top: 5px;
            font-size: 13px;
            word-break: break-word;
        }

        .positive { color: var(--green); }
        .negative { color: #ff9aad; }
        .neutral { color: var(--amber); }

        .empty {
            border: 1px dashed var(--line);
            border-radius: 8px;
            padding: 18px;
            color: var(--muted);
            text-align: center;
        }

        .footer-note {
            margin-top: 20px;
            color: #6f7b8f;
            font-size: 12px;
        }

        @media (max-width: 1100px) {
            .summary,
            .groups {
                grid-template-columns: 1fr;
            }

            .group-stats {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 680px) {
            .page { width: min(100% - 24px, 1380px); }
            .header,
            .toolbar {
                grid-template-columns: 1fr;
                display: grid;
                align-items: stretch;
            }

            button,
            .nav-link {
                width: 100%;
                text-align: center;
            }

            .status { text-align: left; }
        }
    </style>
</head>

<body>
    <main class="page">
        <header class="header">
            <div>
                <div class="logo">NOVAQ <span>AI</span></div>
                <div class="subtitle">Performance Analytics</div>
            </div>
        </header>

        <nav class="top-nav" aria-label="Dashboard navigation">
            <a href="/dashboard">Decision Dashboard</a>
            <a href="/feed-dashboard">Decision Feed</a>
            <a href="/tracking-dashboard">Signal Tracking</a>
            <a href="/performance-dashboard">Performance Analytics</a>
            <a href="/docs">API Docs</a>
        </nav>

        <section class="toolbar">
            <input id="limitInput" type="number" min="1" max="5000" value="1000" />
            <button id="refreshButton" onclick="loadAnalytics()">Refresh</button>
            <div class="status" id="status">READY</div>
        </section>

        <section class="summary" id="summary"></section>
        <section class="panel">
            <div class="panel-title">Insights</div>
            <div class="insights" id="insights"></div>
        </section>

        <section class="groups" id="groups"></section>

        <section class="panel">
            <div class="panel-title">Recent Closed Signals</div>
            <div class="table-wrap" id="recentClosed"></div>
        </section>

        <div class="footer-note">
            Educational analytics only. Not financial advice.
        </div>
    </main>

    <script>
        const limitInput = document.getElementById("limitInput");
        const refreshButton = document.getElementById("refreshButton");
        const statusElement = document.getElementById("status");
        const summaryElement = document.getElementById("summary");
        const insightsElement = document.getElementById("insights");
        const groupsElement = document.getElementById("groups");
        const recentClosedElement = document.getElementById("recentClosed");

        function escapeHtml(value) {
            return String(value ?? "--")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }

        function safeText(value, fallback = "--") {
            if (value === null || value === undefined || value === "") return fallback;
            return String(value);
        }

        function formatPercent(value) {
            if (value === null || value === undefined || value === "") return "--";
            const num = Number(value);
            if (!Number.isNaN(num)) return num.toFixed(4) + "%";
            return String(value);
        }

        function enumBadge(value) {
            return `<span class="badge notranslate">${escapeHtml(safeText(value))}</span>`;
        }

        function formatNumber(value, digits = 4) {
            if (value === null || value === undefined || value === "") return "--";
            const number = Number(value);
            if (!Number.isFinite(number)) return escapeHtml(value);
            return number.toLocaleString("en-US", {
                minimumFractionDigits: 0,
                maximumFractionDigits: digits
            });
        }

        function returnClass(value) {
            const number = Number(value || 0);
            if (number > 0) return "positive";
            if (number < 0) return "negative";
            return "neutral";
        }

        function renderSummary(summary) {
            const cards = [
                ["Total Closed", summary.total],
                ["Winrate", `${formatNumber(summary.winrate_percent, 2)}%`],
                ["Avg Return", `${formatNumber(summary.average_return_percent, 4)}%`],
                ["Best Return", `${formatNumber(summary.best_return_percent, 4)}%`],
                ["Worst Return", `${formatNumber(summary.worst_return_percent, 4)}%`],
                ["Avg Score", formatNumber(summary.average_opportunity_score, 2)]
            ];

            summaryElement.innerHTML = cards.map(([label, value]) => `
                <article class="summary-card">
                    <div class="label">${escapeHtml(label)}</div>
                    <div class="summary-value">${escapeHtml(value)}</div>
                </article>
            `).join("");
        }

        function renderInsights(insights) {
            insightsElement.innerHTML = insights.length
                ? insights.map((item) => `<div class="insight">${escapeHtml(item)}</div>`).join("")
                : `<div class="empty">No insights yet.</div>`;
        }

        function renderGroupTable(title, rows) {
            if (!rows.length) {
                return `
                    <article class="panel">
                        <div class="panel-title">${escapeHtml(title)}</div>
                        <div class="empty">No closed signals in this category.</div>
                    </article>
                `;
            }

            const cards = rows.map((row) => {
                const stats = row.stats || {};
                return `
                    <div class="group-card">
                        <div class="group-key notranslate">${escapeHtml(row.key)}</div>
                        <div class="group-stats">
                            <div class="group-stat"><div class="label">Total</div><strong>${escapeHtml(stats.total)}</strong></div>
                            <div class="group-stat"><div class="label">Winrate</div><strong>${formatNumber(stats.winrate_percent, 2)}%</strong></div>
                            <div class="group-stat"><div class="label">Avg Return</div><strong class="${returnClass(stats.average_return_percent)}">${formatNumber(stats.average_return_percent, 4)}%</strong></div>
                            <div class="group-stat"><div class="label">Best Return</div><strong class="${returnClass(stats.best_return_percent)}">${formatNumber(stats.best_return_percent, 4)}%</strong></div>
                            <div class="group-stat"><div class="label">Worst Return</div><strong class="${returnClass(stats.worst_return_percent)}">${formatNumber(stats.worst_return_percent, 4)}%</strong></div>
                            <div class="group-stat"><div class="label">Avg Score</div><strong>${formatNumber(stats.average_opportunity_score, 2)}</strong></div>
                        </div>
                    </div>
                `;
            }).join("");

            return `
                <article class="panel">
                    <div class="panel-title">${escapeHtml(title)}</div>
                    <div class="group-list">${cards}</div>
                </article>
            `;
        }

        function renderGroups(data) {
            const sections = [
                ["Performance by Action", data.by_action || []],
                ["Performance by Quality", data.by_quality_label || []],
                ["Performance by Risk", data.by_risk_level || []],
                ["Performance by Market State", data.by_market_state || []],
                ["Performance by Signal Trend", data.by_signal_trend || []],
                ["Performance by RSI", data.by_signal_rsi || []],
                ["Performance by Momentum", data.by_signal_momentum || []],
                ["Performance by Symbol", data.by_symbol || []]
            ];

            groupsElement.innerHTML = sections
                .map(([title, rows]) => renderGroupTable(title, rows))
                .join("");
        }

        function renderRecent(signals) {
            if (!signals.length) {
                recentClosedElement.innerHTML = `<div class="empty">No closed paper signals yet.</div>`;
                return;
            }

            const body = signals.map((signal) => `
                <tr>
                    <td class="key">#${escapeHtml(signal.id)}</td>
                    <td>${escapeHtml(signal.symbol)}</td>
                    <td>${enumBadge(signal.action)}</td>
                    <td class="${returnClass(signal.return_percent)}">${formatPercent(signal.return_percent)}</td>
                    <td>${enumBadge(signal.outcome)}</td>
                    <td>${enumBadge(signal.quality_label_value)}</td>
                    <td>${escapeHtml(signal.opportunity_score_value)}</td>
                    <td>${enumBadge(signal.market_state_value)}</td>
                    <td>${enumBadge(signal.signal_trend)} ${enumBadge(signal.signal_rsi)} ${enumBadge(signal.signal_momentum)}</td>
                    <td>${enumBadge(signal.close_reason)}</td>
                </tr>
            `).join("");

            recentClosedElement.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Symbol</th>
                            <th>Action</th>
                            <th>Return</th>
                            <th>Outcome</th>
                            <th>Quality</th>
                            <th>Score</th>
                            <th>Market State</th>
                            <th>Trend / RSI / Momentum</th>
                            <th>Close Reason</th>
                        </tr>
                    </thead>
                    <tbody>${body}</tbody>
                </table>
            `;
        }

        async function loadAnalytics() {
            const limit = limitInput.value || "1000";
            refreshButton.disabled = true;
            statusElement.innerText = "UPDATING";

            try {
                const response = await fetch(`/performance-analytics?limit=${encodeURIComponent(limit)}`);
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail?.message || data.detail || "Analytics unavailable");
                }

                renderSummary(data.summary || {});
                renderInsights(data.insights || []);
                renderGroups(data);
                renderRecent(data.recent_closed_signals || []);
                statusElement.innerText = `UPDATED ${new Date().toLocaleTimeString()}`;
            } catch (error) {
                statusElement.innerText = "ERROR";
                insightsElement.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
            } finally {
                refreshButton.disabled = false;
            }
        }

        loadAnalytics();
    </script>
</body>
</html>
    """


@app.get("/tracking-dashboard", response_class=HTMLResponse)
def tracking_dashboard():
    return """
<!DOCTYPE html>
<html lang="en" translate="no">
<head>
    <meta charset="UTF-8" />
    <title>NOVAQ AI Paper Signal Tracking</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="google" content="notranslate" />

    <style>
        * { box-sizing: border-box; }

        .notranslate {
            unicode-bidi: isolate;
        }

        :root {
            --bg: #070b12;
            --panel: #101722;
            --line: rgba(255, 255, 255, 0.08);
            --text: #f4f7fb;
            --muted: #8d99ae;
            --cyan: #00ffc2;
            --blue: #4b8dff;
            --red: #ff5c7a;
            --amber: #ffd166;
            --green: #62f5a7;
        }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: Inter, Arial, sans-serif;
            background: linear-gradient(180deg, #070b12 0%, #0a101a 54%, #06090f 100%);
            color: var(--text);
        }

        .page {
            width: min(1320px, calc(100% - 40px));
            margin: 0 auto;
            padding: 32px 0 44px;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            gap: 24px;
            margin-bottom: 22px;
        }

        .logo {
            font-size: 30px;
            font-weight: 900;
            line-height: 1;
        }

        .logo span { color: var(--cyan); }

        .subtitle {
            margin-top: 8px;
            color: var(--muted);
            font-size: 15px;
        }

        .top-nav {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 18px;
        }

        .top-nav a {
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            border-radius: 8px;
            padding: 10px 12px;
            text-decoration: none;
            font-size: 12px;
            font-weight: 900;
            white-space: nowrap;
        }

        .top-nav a:hover {
            filter: brightness(1.08);
        }

        .status {
            color: var(--cyan);
            border: 1px solid rgba(0, 255, 194, 0.24);
            background: rgba(0, 255, 194, 0.07);
            border-radius: 8px;
            padding: 9px 12px;
            font-size: 12px;
            font-weight: 800;
            white-space: nowrap;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
            justify-content: flex-end;
        }

        .nav-link {
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            border-radius: 8px;
            padding: 9px 12px;
            text-decoration: none;
            font-size: 12px;
            font-weight: 900;
            white-space: nowrap;
        }

        .toolbar {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto auto;
            gap: 12px;
            align-items: center;
            background: rgba(16, 23, 34, 0.9);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 18px;
        }

        .evaluation-panel {
            background: rgba(16, 23, 34, 0.9);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 18px;
        }

        .evaluation-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
            gap: 12px;
            align-items: end;
        }

        .evaluation-status {
            margin-top: 10px;
            color: #b7c2d3;
            font-size: 12px;
        }

        input {
            width: 100%;
            min-width: 0;
            border: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.045);
            color: var(--text);
            padding: 13px 14px;
            border-radius: 8px;
            outline: none;
            font-size: 14px;
            font-weight: 700;
        }

        button {
            border: 0;
            border-radius: 8px;
            padding: 13px 18px;
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            cursor: pointer;
            font-weight: 900;
            white-space: nowrap;
        }

        button:disabled {
            cursor: wait;
            opacity: 0.7;
        }

        .close-button {
            background: rgba(255, 209, 102, 0.92);
            padding: 10px 12px;
            font-size: 12px;
        }

        .summary {
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 18px;
        }

        .summary-card,
        .signal-card {
            background: rgba(16, 23, 34, 0.92);
            border: 1px solid var(--line);
            border-radius: 8px;
        }

        .summary-card {
            min-height: 86px;
            padding: 15px;
        }

        .label {
            color: var(--muted);
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
        }

        .summary-value {
            margin-top: 10px;
            font-size: 26px;
            font-weight: 950;
            overflow-wrap: anywhere;
        }

        .signals-list {
            display: grid;
            gap: 12px;
        }

        .signal-card {
            padding: 16px;
        }

        .signal-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 14px;
            margin-bottom: 14px;
        }

        .symbol {
            font-size: 22px;
            font-weight: 950;
        }

        .badges {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: flex-end;
        }

        .badge {
            border-radius: 8px;
            padding: 8px 10px;
            min-width: 72px;
            text-align: center;
            font-size: 12px;
            font-weight: 950;
            border: 1px solid var(--line);
        }

        .badge-open { color: var(--cyan); background: rgba(0, 255, 194, 0.12); }
        .badge-closed { color: #9fbeff; background: rgba(75, 141, 255, 0.12); }
        .badge-win { color: var(--green); background: rgba(98, 245, 167, 0.12); }
        .badge-loss { color: #ff9aad; background: rgba(255, 92, 122, 0.12); }
        .badge-flat { color: var(--amber); background: rgba(255, 209, 102, 0.12); }

        .metrics {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 8px;
            margin-bottom: 12px;
        }

        .metric {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 10px;
            background: rgba(255, 255, 255, 0.035);
            min-width: 0;
        }

        .metric strong {
            display: block;
            margin-top: 6px;
            font-size: 14px;
            overflow-wrap: anywhere;
        }

        .time-row {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
            margin-top: 8px;
        }

        .empty {
            border: 1px dashed var(--line);
            border-radius: 8px;
            padding: 24px;
            color: var(--muted);
            text-align: center;
        }

        .footer-note {
            margin-top: 20px;
            color: #6f7b8f;
            font-size: 12px;
        }

        @media (max-width: 1040px) {
            .summary,
            .metrics {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 680px) {
            .page { width: min(100% - 24px, 1320px); }

            .header,
            .toolbar,
            .evaluation-grid,
            .time-row {
                display: grid;
                grid-template-columns: 1fr;
                align-items: stretch;
            }

            button { width: 100%; }
        }
    </style>
</head>

<body>
    <main class="page">
        <header class="header">
            <div>
                <div class="logo">NOVAQ <span>AI</span></div>
                <div class="subtitle">Paper Signal Tracking</div>
            </div>
            <div class="header-actions">
                <div class="status notranslate" id="status">READY</div>
            </div>
        </header>

        <nav class="top-nav" aria-label="Dashboard navigation">
            <a href="/dashboard">Decision Dashboard</a>
            <a href="/feed-dashboard">Decision Feed</a>
            <a href="/tracking-dashboard">Signal Tracking</a>
            <a href="/performance-dashboard">Performance Analytics</a>
            <a href="/docs">API Docs</a>
        </nav>

        <section class="toolbar">
            <input id="symbolInput" value="BTCUSDT" />
            <button id="trackButton" onclick="trackSignal()">Track Signal</button>
            <button id="refreshButton" onclick="loadTracking()">Refresh</button>
        </section>

        <section class="evaluation-panel">
            <div class="label">Auto Evaluation Settings</div>
            <div class="evaluation-grid">
                <div>
                    <div class="label">Take Profit %</div>
                    <input id="takeProfitInput" type="number" step="0.01" value="1.0" />
                </div>
                <div>
                    <div class="label">Stop Loss %</div>
                    <input id="stopLossInput" type="number" step="0.01" value="-0.7" />
                </div>
                <div>
                    <div class="label">Max Age Minutes</div>
                    <input id="maxAgeInput" type="number" step="1" value="60" />
                </div>
                <button id="evaluateButton" onclick="evaluateOpenSignals()">Evaluate Open Signals</button>
            </div>
            <div class="evaluation-status" id="evaluationStatus">Evaluation runs only when you press the button.</div>
        </section>

        <section class="summary" id="summary"></section>
        <section class="signals-list" id="signalsList"></section>

        <div class="footer-note">
            Paper tracking only. Educational signal simulation, not real trading and not financial advice.
        </div>
    </main>

    <script>
        const summaryElement = document.getElementById("summary");
        const listElement = document.getElementById("signalsList");
        const statusElement = document.getElementById("status");
        const symbolInput = document.getElementById("symbolInput");
        const trackButton = document.getElementById("trackButton");
        const refreshButton = document.getElementById("refreshButton");
        const takeProfitInput = document.getElementById("takeProfitInput");
        const stopLossInput = document.getElementById("stopLossInput");
        const maxAgeInput = document.getElementById("maxAgeInput");
        const evaluateButton = document.getElementById("evaluateButton");
        const evaluationStatus = document.getElementById("evaluationStatus");

        function escapeHtml(value) {
            return String(value ?? "--")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }

        function safeText(value, fallback = "--") {
            if (value === null || value === undefined || value === "") return fallback;
            return String(value);
        }

        function formatPercent(value) {
            if (value === null || value === undefined || value === "") return "--";
            const num = Number(value);
            if (!Number.isNaN(num)) return num.toFixed(4) + "%";
            return String(value);
        }

        function enumBadge(value) {
            return `<span class="badge notranslate">${escapeHtml(safeText(value))}</span>`;
        }

        function formatNumber(value, digits = 4) {
            if (value === null || value === undefined || value === "") return "--";
            const number = Number(value);
            if (!Number.isFinite(number)) return escapeHtml(value);
            return number.toLocaleString("en-US", {
                minimumFractionDigits: 0,
                maximumFractionDigits: digits
            });
        }

        function badgeClass(value) {
            const normalized = String(value || "").toLowerCase();
            if (normalized === "open") return "badge-open";
            if (normalized === "closed") return "badge-closed";
            if (normalized === "win") return "badge-win";
            if (normalized === "loss") return "badge-loss";
            return "badge-flat";
        }

        function renderSummary(summary) {
            const cards = [
                ["Total", summary.total],
                ["Open", summary.open],
                ["Closed", summary.closed],
                ["Winrate", `${formatNumber(summary.winrate_percent, 2)}%`],
                ["Avg Return", `${formatNumber(summary.average_return_percent, 4)}%`],
                ["Best Return", `${formatNumber(summary.best_return_percent, 4)}%`],
                ["Worst Return", `${formatNumber(summary.worst_return_percent, 4)}%`],
                ["TP Closed", summary.take_profit_closed],
                ["SL Closed", summary.stop_loss_closed],
                ["Max Age", summary.max_age_closed],
                ["Manual", summary.manual_closed]
            ];

            summaryElement.innerHTML = cards.map(([label, value]) => `
                <article class="summary-card">
                    <div class="label">${escapeHtml(label)}</div>
                    <div class="summary-value">${escapeHtml(value)}</div>
                </article>
            `).join("");
        }

        function renderSignal(signal) {
            const closeButton = signal.status === "OPEN"
                ? `<button class="close-button" onclick="closeSignal(${Number(signal.id)})">Close</button>`
                : "";

            return `
                <article class="signal-card">
                    <div class="signal-top">
                        <div>
                            <div class="symbol">#${escapeHtml(signal.id)} ${escapeHtml(signal.symbol)}</div>
                            <div class="label">Paper signal</div>
                        </div>
                        <div class="badges">
                            <div class="badge ${badgeClass(signal.status)} notranslate">${escapeHtml(safeText(signal.status))}</div>
                            <div class="badge ${badgeClass(signal.outcome)} notranslate">${escapeHtml(safeText(signal.outcome, "PENDING"))}</div>
                            ${closeButton}
                        </div>
                    </div>

                    <div class="metrics">
                        <div class="metric"><div class="label">Action</div><strong>${enumBadge(signal.action)}</strong></div>
                        <div class="metric"><div class="label">Entry Price</div><strong>$${formatNumber(signal.entry_price, 6)}</strong></div>
                        <div class="metric"><div class="label">Exit Price</div><strong>${signal.exit_price == null ? "--" : "$" + formatNumber(signal.exit_price, 6)}</strong></div>
                        <div class="metric"><div class="label">Return %</div><strong>${formatPercent(signal.return_percent)}</strong></div>
                        <div class="metric"><div class="label">Position</div><strong>${escapeHtml(signal.position_size)}</strong></div>
                    </div>

                    <div class="metrics">
                        <div class="metric"><div class="label">Confidence</div><strong>${escapeHtml(signal.confidence)}%</strong></div>
                        <div class="metric"><div class="label">Opportunity Score</div><strong>${escapeHtml(signal.opportunity_score)}/100</strong></div>
                        <div class="metric"><div class="label">Signal Quality</div><strong>${enumBadge(signal.quality_label)}</strong></div>
                        <div class="metric"><div class="label">Risk Level</div><strong>${enumBadge(signal.risk_level)}</strong></div>
                        <div class="metric"><div class="label">Tier</div><strong>${escapeHtml(signal.tier)} / 5</strong></div>
                    </div>

                    <div class="metrics">
                        <div class="metric"><div class="label">Close Reason</div><strong>${enumBadge(signal.close_reason)}</strong></div>
                        <div class="metric"><div class="label">Age Minutes</div><strong>${signal.age_minutes == null ? "--" : formatNumber(signal.age_minutes, 4)}</strong></div>
                        <div class="metric"><div class="label">Outcome</div><strong>${enumBadge(signal.outcome || "PENDING")}</strong></div>
                        <div class="metric"><div class="label">Status</div><strong>${enumBadge(signal.status)}</strong></div>
                        <div class="metric"><div class="label">Time Horizon</div><strong>${escapeHtml(signal.time_horizon)}</strong></div>
                    </div>

                    <div class="time-row">
                        <div class="metric"><div class="label">Entry Time UTC</div><strong>${escapeHtml(signal.entry_time_utc)}</strong></div>
                        <div class="metric"><div class="label">Exit Time UTC</div><strong>${escapeHtml(signal.exit_time_utc)}</strong></div>
                    </div>
                </article>
            `;
        }

        async function trackSignal() {
            const symbol = symbolInput.value.trim() || "BTCUSDT";
            trackButton.disabled = true;
            statusElement.innerText = "TRACKING";

            try {
                const response = await fetch(`/track/${encodeURIComponent(symbol)}`, { method: "POST" });
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail?.message || data.detail || "Signal could not be tracked");
                }

                statusElement.innerText = `TRACKED #${data.id}`;
                await loadTracking();
            } catch (error) {
                alert(error.message);
                statusElement.innerText = "ERROR";
            } finally {
                trackButton.disabled = false;
            }
        }

        async function closeSignal(id) {
            statusElement.innerText = "CLOSING";

            try {
                const response = await fetch(`/tracked-signals/${encodeURIComponent(id)}/close`, { method: "POST" });
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail?.message || data.detail || "Signal could not be closed");
                }

                statusElement.innerText = `CLOSED #${data.id}`;
                await loadTracking();
            } catch (error) {
                alert(error.message);
                statusElement.innerText = "ERROR";
            }
        }

        async function evaluateOpenSignals() {
            evaluateButton.disabled = true;
            statusElement.innerText = "EVALUATING";
            evaluationStatus.innerText = "Evaluating open paper signals...";

            const params = new URLSearchParams({
                take_profit_percent: takeProfitInput.value || "1.0",
                stop_loss_percent: stopLossInput.value || "-0.7",
                max_age_minutes: maxAgeInput.value || "60"
            });

            try {
                const response = await fetch(`/evaluate-open-signals?${params.toString()}`, { method: "POST" });
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail?.message || data.detail || "Evaluation failed");
                }

                const message = `Evaluated ${data.evaluated}, closed ${data.closed}, still open ${data.still_open}`;
                evaluationStatus.innerText = message;
                statusElement.innerText = "EVALUATED";
                alert(message);
                await loadTracking();
            } catch (error) {
                evaluationStatus.innerText = error.message;
                statusElement.innerText = "ERROR";
            } finally {
                evaluateButton.disabled = false;
            }
        }

        async function loadTracking() {
            refreshButton.disabled = true;
            statusElement.innerText = "UPDATING";

            try {
                const [summaryResponse, signalsResponse] = await Promise.all([
                    fetch("/tracking-summary"),
                    fetch("/tracked-signals?limit=100")
                ]);

                const summary = await summaryResponse.json();
                const signals = await signalsResponse.json();

                if (!summaryResponse.ok) {
                    throw new Error(summary.detail?.message || summary.detail || "Summary unavailable");
                }
                if (!signalsResponse.ok) {
                    throw new Error(signals.detail?.message || signals.detail || "Signals unavailable");
                }

                renderSummary(summary);
                listElement.innerHTML = (signals.signals || []).length
                    ? signals.signals.map(renderSignal).join("")
                    : `<div class="empty">No paper signals tracked yet.</div>`;

                statusElement.innerText = `UPDATED ${new Date().toLocaleTimeString()}`;
            } catch (error) {
                listElement.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
                statusElement.innerText = "ERROR";
            } finally {
                refreshButton.disabled = false;
            }
        }

        loadTracking();
        setInterval(loadTracking, 30000);
    </script>
</body>
</html>
    """


@app.get("/feed-dashboard", response_class=HTMLResponse)
def feed_dashboard():
    return """
<!DOCTYPE html>
<html lang="en" translate="no">
<head>
    <meta charset="UTF-8" />
    <title>NOVAQ AI Decision Feed</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="google" content="notranslate" />

    <style>
        * { box-sizing: border-box; }

        .notranslate {
            unicode-bidi: isolate;
        }

        :root {
            --bg: #070b12;
            --panel: #101722;
            --panel-soft: #0c121c;
            --line: rgba(255, 255, 255, 0.08);
            --text: #f4f7fb;
            --muted: #8d99ae;
            --cyan: #00ffc2;
            --blue: #4b8dff;
            --red: #ff5c7a;
            --amber: #ffd166;
        }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: Inter, Arial, sans-serif;
            background: linear-gradient(180deg, #070b12 0%, #0a101a 52%, #06090f 100%);
            color: var(--text);
        }

        .page {
            width: min(1320px, calc(100% - 40px));
            margin: 0 auto;
            padding: 32px 0 44px;
        }

        .header {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 24px;
            margin-bottom: 22px;
        }

        .logo {
            font-size: 30px;
            font-weight: 900;
            line-height: 1;
        }

        .logo span { color: var(--cyan); }

        .subtitle {
            margin-top: 8px;
            color: var(--muted);
            font-size: 15px;
        }

        .top-nav {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 18px;
        }

        .top-nav a {
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            border-radius: 8px;
            padding: 10px 12px;
            text-decoration: none;
            font-size: 12px;
            font-weight: 900;
            white-space: nowrap;
        }

        .top-nav a:hover {
            filter: brightness(1.08);
        }

        .status {
            color: var(--cyan);
            border: 1px solid rgba(0, 255, 194, 0.24);
            background: rgba(0, 255, 194, 0.07);
            border-radius: 8px;
            padding: 9px 12px;
            font-size: 12px;
            font-weight: 800;
            white-space: nowrap;
        }

        .toolbar {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 12px;
            align-items: center;
            background: rgba(16, 23, 34, 0.9);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 18px;
        }

        input {
            width: 100%;
            min-width: 0;
            border: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.045);
            color: var(--text);
            padding: 13px 14px;
            border-radius: 8px;
            outline: none;
            font-size: 14px;
            font-weight: 700;
        }

        button {
            border: 0;
            border-radius: 8px;
            padding: 13px 18px;
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            cursor: pointer;
            font-weight: 900;
            white-space: nowrap;
        }

        button:disabled {
            cursor: wait;
            opacity: 0.72;
        }

        .track-button {
            width: 100%;
            padding: 9px 12px;
            font-size: 12px;
        }

        .summary {
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 18px;
        }

        .summary-card,
        .asset-card {
            background: rgba(16, 23, 34, 0.92);
            border: 1px solid var(--line);
            border-radius: 8px;
        }

        .summary-card {
            padding: 15px;
            min-height: 86px;
        }

        .label {
            color: var(--muted);
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
        }

        .summary-value {
            margin-top: 10px;
            font-size: 30px;
            font-weight: 950;
        }

        .feed-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
        }

        .asset-card {
            padding: 16px;
            min-width: 0;
        }

        .asset-top {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 14px;
        }

        .symbol {
            font-size: 22px;
            font-weight: 950;
        }

        .action {
            border-radius: 8px;
            padding: 8px 11px;
            font-weight: 950;
            font-size: 13px;
            min-width: 72px;
            text-align: center;
        }

        .action-buy { background: rgba(0, 255, 194, 0.12); color: var(--cyan); }
        .action-sell { background: rgba(255, 92, 122, 0.13); color: var(--red); }
        .action-hold { background: rgba(75, 141, 255, 0.12); color: #9fbeff; }
        .action-wait { background: rgba(255, 209, 102, 0.12); color: var(--amber); }

        .badge-stack {
            display: grid;
            gap: 8px;
            justify-items: end;
        }

        .quality-badge {
            border-radius: 8px;
            border: 1px solid var(--line);
            padding: 7px 10px;
            font-size: 12px;
            font-weight: 950;
            text-align: center;
            min-width: 72px;
        }

        .quality-top { color: var(--cyan); background: rgba(0, 255, 194, 0.12); }
        .quality-strong { color: #9fbeff; background: rgba(75, 141, 255, 0.12); }
        .quality-normal { color: var(--amber); background: rgba(255, 209, 102, 0.12); }
        .quality-weak { color: #ff9aad; background: rgba(255, 92, 122, 0.12); }

        .badge {
            display: inline-block;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 6px 8px;
            background: rgba(255, 255, 255, 0.045);
            color: #e3eaf5;
            font-size: 12px;
            font-weight: 900;
        }

        .score-panel {
            display: flex;
            justify-content: space-between;
            gap: 14px;
            align-items: center;
            border: 1px solid rgba(0, 255, 194, 0.16);
            border-radius: 8px;
            padding: 12px;
            background: linear-gradient(135deg, rgba(0, 255, 194, 0.08), rgba(75, 141, 255, 0.055));
            margin-bottom: 12px;
        }

        .score-value {
            font-size: 26px;
            font-weight: 950;
        }

        .score-note {
            color: #b7c2d3;
            font-size: 12px;
            line-height: 1.45;
            text-align: right;
        }

        .metrics {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
            margin-bottom: 12px;
        }

        .metric {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 10px;
            background: rgba(255, 255, 255, 0.035);
            min-width: 0;
        }

        .metric strong {
            display: block;
            margin-top: 6px;
            font-size: 15px;
            overflow-wrap: anywhere;
        }

        .signal-row {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
            margin-bottom: 12px;
        }

        .pill {
            border-radius: 8px;
            border: 1px solid var(--line);
            padding: 9px 10px;
            color: #dce5f3;
            background: rgba(255, 255, 255, 0.035);
            font-size: 13px;
            overflow-wrap: anywhere;
        }

        .copy-block {
            border-top: 1px solid var(--line);
            padding-top: 12px;
            display: grid;
            gap: 10px;
        }

        .copy-block p {
            margin: 5px 0 0;
            color: #d7deea;
            line-height: 1.45;
            font-size: 13px;
        }

        .error {
            margin-top: 12px;
            color: #ff9aad;
            font-size: 12px;
            line-height: 1.45;
            overflow-wrap: anywhere;
        }

        .empty {
            border: 1px dashed var(--line);
            border-radius: 8px;
            padding: 24px;
            color: var(--muted);
            text-align: center;
        }

        .footer-note {
            margin-top: 20px;
            color: #6f7b8f;
            font-size: 12px;
        }

        @media (max-width: 980px) {
            .summary,
            .feed-grid {
                grid-template-columns: 1fr;
            }

            .metrics,
            .signal-row {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 620px) {
            .page { width: min(100% - 24px, 1320px); }
            .header,
            .toolbar {
                grid-template-columns: 1fr;
                align-items: stretch;
            }

            .header {
                display: grid;
            }

            button { width: 100%; }
        }
    </style>
</head>

<body>
    <main class="page">
        <header class="header">
            <div>
                <div class="logo">NOVAQ <span>AI</span></div>
                <div class="subtitle">What To Do Now Feed</div>
            </div>
            <div class="status notranslate" id="status">READY</div>
        </header>

        <nav class="top-nav" aria-label="Dashboard navigation">
            <a href="/dashboard">Decision Dashboard</a>
            <a href="/feed-dashboard">Decision Feed</a>
            <a href="/tracking-dashboard">Signal Tracking</a>
            <a href="/performance-dashboard">Performance Analytics</a>
            <a href="/docs">API Docs</a>
        </nav>

        <section class="toolbar">
            <input
                id="symbolsInput"
                value="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,AVAXUSDT,LINKUSDT,TONUSDT"
            />
            <button id="refreshButton" onclick="loadFeed()">Refresh</button>
        </section>

        <section class="summary" id="summary"></section>
        <section class="feed-grid" id="feedGrid"></section>

        <div class="footer-note">
            Educational signal only. Not financial advice.
        </div>
    </main>

    <script>
        const summaryElement = document.getElementById("summary");
        const gridElement = document.getElementById("feedGrid");
        const statusElement = document.getElementById("status");
        const refreshButton = document.getElementById("refreshButton");
        const symbolsInput = document.getElementById("symbolsInput");

        function escapeHtml(value) {
            return String(value ?? "--")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }

        function safeText(value, fallback = "--") {
            if (value === null || value === undefined || value === "") return fallback;
            return String(value);
        }

        function formatPercent(value) {
            if (value === null || value === undefined || value === "") return "--";
            const num = Number(value);
            if (!Number.isNaN(num)) return num.toFixed(4) + "%";
            return String(value);
        }

        function enumBadge(value) {
            return `<span class="badge notranslate">${escapeHtml(safeText(value))}</span>`;
        }

        function actionClass(action) {
            const normalized = String(action || "WAIT").toLowerCase();
            if (normalized === "buy") return "action-buy";
            if (normalized === "sell") return "action-sell";
            if (normalized === "hold") return "action-hold";
            return "action-wait";
        }

        function qualityClass(label) {
            const normalized = String(label || "WEAK").toLowerCase();
            if (normalized === "top") return "quality-top";
            if (normalized === "strong") return "quality-strong";
            if (normalized === "normal") return "quality-normal";
            return "quality-weak";
        }

        async function trackFeedSignal(symbol) {
            try {
                const response = await fetch(`/track/${encodeURIComponent(symbol)}`, { method: "POST" });
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail?.message || data.detail || "Signal could not be tracked");
                }

                alert("Signal tracked");
            } catch (error) {
                alert(error.message);
            }
        }

        function renderSummary(summary) {
            const cards = [
                ["Total", summary.total],
                ["BUY", summary.buy],
                ["SELL", summary.sell],
                ["HOLD", summary.hold],
                ["WAIT", summary.wait],
                ["Top Score", summary.top_score ?? "--"],
                ["Top Quality", summary.top_quality ?? "--"]
            ];

            summaryElement.innerHTML = cards.map(([label, value]) => `
                <article class="summary-card">
                    <div class="label">${escapeHtml(label)}</div>
                    <div class="summary-value">${escapeHtml(value)}</div>
                </article>
            `).join("");
        }

        function renderAsset(item) {
            const marketState = item.market_state?.state || "--";
            const signalSet = item.signals?.signals || {};
            const opportunityScore = item.opportunity_score ?? 0;
            const qualityLabel = item.quality_label || "WEAK";
            const errorBlock = item.error
                ? `<div class="error">${escapeHtml(item.error)}</div>`
                : "";

            return `
                <article class="asset-card">
                    <div class="asset-top">
                        <div>
                            <div class="symbol">${escapeHtml(item.symbol)}</div>
                            <div class="label">Tier ${escapeHtml(item.tier)} / 5</div>
                        </div>
                        <div class="badge-stack">
                            <div class="action ${actionClass(item.action)} notranslate">${escapeHtml(safeText(item.action))}</div>
                            <div class="quality-badge ${qualityClass(qualityLabel)} notranslate">${escapeHtml(safeText(qualityLabel))}</div>
                            <button class="track-button" data-symbol="${escapeHtml(item.symbol)}" onclick="trackFeedSignal(this.dataset.symbol)">Track</button>
                        </div>
                    </div>

                    <div class="score-panel">
                        <div>
                            <div class="label">Opportunity Score</div>
                            <div class="score-value">Score ${escapeHtml(opportunityScore)}/100</div>
                        </div>
                        <div class="score-note">${escapeHtml(item.why_ranked)}</div>
                    </div>

                    <div class="metrics">
                        <div class="metric"><div class="label">Confidence</div><strong>${escapeHtml(item.confidence)}%</strong></div>
                        <div class="metric"><div class="label">Expected Return</div><strong>${escapeHtml(item.expected_return)}</strong></div>
                        <div class="metric"><div class="label">Risk Level</div><strong>${enumBadge(item.risk_level)}</strong></div>
                        <div class="metric"><div class="label">Position Size</div><strong>${escapeHtml(item.position_size)}</strong></div>
                    </div>

                    <div class="signal-row">
                        <div class="pill"><span class="label">Market State</span><br>${enumBadge(marketState)}</div>
                        <div class="pill"><span class="label">Trend</span><br>${enumBadge(signalSet.trend)}</div>
                        <div class="pill"><span class="label">RSI</span><br>${enumBadge(signalSet.rsi)}</div>
                        <div class="pill"><span class="label">Momentum</span><br>${enumBadge(signalSet.momentum)}</div>
                    </div>

                    <div class="copy-block">
                        <div><div class="label">Why Ranked</div><p>${escapeHtml(item.why_ranked)}</p></div>
                        <div><div class="label">Reasoning</div><p>${escapeHtml(item.reasoning)}</p></div>
                        <div><div class="label">Failure Scenario</div><p>${escapeHtml(item.failure_scenario)}</p></div>
                        <div><div class="label">Safer Alternative</div><p>${escapeHtml(item.alternative_action)}</p></div>
                    </div>

                    ${errorBlock}
                </article>
            `;
        }

        async function loadFeed() {
            const symbols = symbolsInput.value.trim();
            const url = symbols ? `/feed?symbols=${encodeURIComponent(symbols)}` : "/feed";

            refreshButton.disabled = true;
            statusElement.innerText = "UPDATING";

            try {
                const response = await fetch(url);
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail?.message || "Feed unavailable");
                }

                renderSummary(data.summary || {});
                const results = data.results || [];
                gridElement.innerHTML = results.length
                    ? results.map(renderAsset).join("")
                    : `<div class="empty">No feed results available.</div>`;

                statusElement.innerText = `UPDATED ${new Date().toLocaleTimeString()}`;
            } catch (error) {
                gridElement.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
                statusElement.innerText = "ERROR";
            } finally {
                refreshButton.disabled = false;
            }
        }

        loadFeed();
        setInterval(loadFeed, 60000);
    </script>
</body>
</html>
    """


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
<!DOCTYPE html>
<html lang="en" translate="no">
<head>
    <meta charset="UTF-8" />
    <title>NOVAQ AI Trading Intelligence</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="google" content="notranslate" />

    <style>
        * { box-sizing: border-box; }

        .notranslate {
            unicode-bidi: isolate;
        }

        body {
            margin: 0;
            font-family: Inter, Arial, sans-serif;
            background:
                radial-gradient(circle at top left, rgba(0, 255, 194, 0.16), transparent 30%),
                radial-gradient(circle at top right, rgba(91, 141, 255, 0.16), transparent 35%),
                #070b12;
            color: #f3f6fb;
            min-height: 100vh;
        }

        .page {
            max-width: 1180px;
            margin: 0 auto;
            padding: 40px 24px;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 24px;
            margin-bottom: 34px;
        }

        .logo {
            font-size: 30px;
            font-weight: 900;
            letter-spacing: -0.04em;
        }

        .logo span { color: #00ffc2; }

        .subtitle {
            color: #8d99ae;
            margin-top: 8px;
        }

        .top-nav {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 24px;
        }

        .top-nav a {
            color: #031018;
            background: linear-gradient(135deg, #00ffc2, #4b8dff);
            border-radius: 8px;
            padding: 10px 12px;
            text-decoration: none;
            font-size: 12px;
            font-weight: 900;
            white-space: nowrap;
        }

        .top-nav a:hover {
            filter: brightness(1.08);
        }

        .status {
            padding: 10px 14px;
            border: 1px solid rgba(0, 255, 194, 0.25);
            background: rgba(0, 255, 194, 0.08);
            color: #00ffc2;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 800;
        }

        .hero {
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 22px;
        }

        .card {
            background: rgba(12, 18, 30, 0.86);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 28px;
            padding: 26px;
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.38);
            backdrop-filter: blur(18px);
        }

        .decision-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 20px;
            margin-bottom: 28px;
        }

        .label {
            color: #8d99ae;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            margin-bottom: 8px;
        }

        .action {
            font-size: 64px;
            font-weight: 950;
            letter-spacing: -0.06em;
            line-height: 1;
        }

        .symbol {
            color: #8d99ae;
            font-size: 16px;
            margin-top: 10px;
        }

        .confidence { text-align: right; }

        .confidence-number {
            font-size: 42px;
            font-weight: 950;
            color: #00ffc2;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 14px;
            margin-bottom: 22px;
        }

        .metric {
            background: rgba(255, 255, 255, 0.045);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 18px;
            padding: 16px;
        }

        .metric-value {
            font-size: 22px;
            font-weight: 850;
        }

        .badge {
            display: inline-block;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 5px 8px;
            background: rgba(255, 255, 255, 0.045);
            color: #e3eaf5;
            font-size: 12px;
            font-weight: 900;
        }

        .text-block {
            margin-top: 16px;
            padding: 18px;
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
        }

        .text-block p {
            margin: 0;
            line-height: 1.55;
            color: #d7deea;
        }

        .input-row {
            display: flex;
            gap: 10px;
            margin-bottom: 22px;
        }

        input {
            width: 100%;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(255, 255, 255, 0.05);
            color: #fff;
            padding: 14px 16px;
            border-radius: 16px;
            outline: none;
            font-size: 15px;
            font-weight: 700;
        }

        button {
            border: none;
            background: linear-gradient(135deg, #00ffc2, #4b8dff);
            color: #031018;
            font-weight: 950;
            padding: 14px 18px;
            border-radius: 16px;
            cursor: pointer;
            white-space: nowrap;
        }

        .price {
            font-size: 38px;
            font-weight: 950;
            letter-spacing: -0.04em;
            margin-bottom: 18px;
        }

        .small-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .row {
            display: flex;
            justify-content: space-between;
            color: #c8d1df;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            padding-bottom: 10px;
            gap: 16px;
        }

        .row span:first-child { color: #8d99ae; }

        .footer-note {
            margin-top: 22px;
            color: #6f7b8f;
            font-size: 12px;
            line-height: 1.5;
        }

        @media (max-width: 860px) {
            .hero { grid-template-columns: 1fr; }
            .grid { grid-template-columns: 1fr; }
            .action { font-size: 46px; }
            .header {
                flex-direction: column;
                align-items: flex-start;
            }
        }
    </style>
</head>

<body>
    <main class="page">
        <header class="header">
            <div>
                <div class="logo">NOVAQ <span>AI</span></div>
                <div class="subtitle">Real-Time Crypto Decision Intelligence</div>
            </div>
            <div class="status notranslate">LIVE MARKET DATA</div>
        </header>

        <nav class="top-nav" aria-label="Dashboard navigation">
            <a href="/dashboard">Decision Dashboard</a>
            <a href="/feed-dashboard">Decision Feed</a>
            <a href="/tracking-dashboard">Signal Tracking</a>
            <a href="/performance-dashboard">Performance Analytics</a>
            <a href="/docs">API Docs</a>
        </nav>

        <section class="hero">
            <div class="card">
                <div class="decision-top">
                    <div>
                        <div class="label">What to do now</div>
                        <div class="action notranslate" id="action">LOADING</div>
                        <div class="symbol notranslate" id="symbol">BTCUSDT</div>
                    </div>

                    <div class="confidence">
                        <div class="label">Confidence</div>
                        <div class="confidence-number" id="confidence">--%</div>
                    </div>
                </div>

                <div class="grid">
                    <div class="metric">
                        <div class="label">Expected Return</div>
                        <div class="metric-value" id="expectedReturn">--</div>
                    </div>

                    <div class="metric">
                        <div class="label">Risk Level</div>
                        <div class="metric-value notranslate" id="riskLevel">--</div>
                    </div>

                    <div class="metric">
                        <div class="label">Position Size</div>
                        <div class="metric-value" id="positionSize">--</div>
                    </div>
                </div>

                <div class="text-block">
                    <div class="label">Reasoning</div>
                    <p id="reasoning">Loading decision...</p>
                </div>

                <div class="text-block">
                    <div class="label">Failure Scenario</div>
                    <p id="failureScenario">Loading risk scenario...</p>
                </div>

                <div class="text-block">
                    <div class="label">Safer Alternative</div>
                    <p id="alternativeAction">Loading alternative...</p>
                </div>
            </div>

            <aside class="card">
                <div class="input-row">
                    <input id="symbolInput" value="BTCUSDT" />
                    <button onclick="loadDecision()">Analyze</button>
                </div>

                <div class="label">Current Price</div>
                <div class="price" id="price">$--</div>

                <div class="small-list">
                    <div class="row"><span>24h Change</span><strong id="change24h">--</strong></div>
                    <div class="row"><span>24h High</span><strong id="high24h">--</strong></div>
                    <div class="row"><span>24h Low</span><strong id="low24h">--</strong></div>
                    <div class="row"><span>Volume</span><strong id="volume24h">--</strong></div>
                    <div class="row"><span>Data Source</span><strong class="notranslate" id="source">--</strong></div>
                    <div class="row"><span>Tier</span><strong class="notranslate" id="tier">--</strong></div>
                </div>

                <div class="footer-note">
                    Educational signal only. NOVAQ AI does not access user funds and does not execute trades.
                </div>
            </aside>
        </section>
    </main>

    <script>
        function safeText(value, fallback = "--") {
            if (value === null || value === undefined || value === "") return fallback;
            return String(value);
        }

        function formatPercent(value) {
            if (value === null || value === undefined || value === "") return "--";
            const num = Number(value);
            if (!Number.isNaN(num)) return num.toFixed(4) + "%";
            return String(value);
        }

        function enumBadge(value) {
            return `<span class="badge notranslate">${safeText(value)}</span>`;
        }

        async function loadDecision() {
            const symbol = document.getElementById("symbolInput").value || "BTCUSDT";

            const response = await fetch(`/decision/${symbol}`);
            const data = await response.json();

            if (!response.ok) {
                alert("Market data unavailable. Decision must be WAIT.");
                return;
            }

            document.getElementById("action").innerText = safeText(data.action);
            document.getElementById("symbol").innerText = safeText(data.symbol);
            document.getElementById("confidence").innerText = data.confidence + "%";
            document.getElementById("expectedReturn").innerText = data.expected_return;
            document.getElementById("riskLevel").innerHTML = enumBadge(data.risk_level);
            document.getElementById("positionSize").innerText = data.position_size;
            document.getElementById("reasoning").innerText = data.reasoning;
            document.getElementById("failureScenario").innerText = data.failure_scenario;
            document.getElementById("alternativeAction").innerText = data.alternative_action;

            document.getElementById("price").innerText = "$" + Number(data.market.price).toLocaleString("en-US", { maximumFractionDigits: 2 });
            document.getElementById("change24h").innerText = formatPercent(data.market.price_change_percent_24h);
            document.getElementById("high24h").innerText = "$" + Number(data.market.high_24h).toLocaleString("en-US", { maximumFractionDigits: 2 });
            document.getElementById("low24h").innerText = "$" + Number(data.market.low_24h).toLocaleString("en-US", { maximumFractionDigits: 2 });
            document.getElementById("volume24h").innerText = "$" + Number(data.market.quote_volume_24h).toLocaleString("en-US", { maximumFractionDigits: 0 });
            document.getElementById("source").innerText = safeText(data.market.source);
            document.getElementById("tier").innerText = data.tier + "/5";
        }

        loadDecision();
        setInterval(loadDecision, 30000);
    </script>
</body>
</html>
    """
