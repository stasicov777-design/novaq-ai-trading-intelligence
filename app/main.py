from datetime import datetime, timezone
from html import escape
from urllib.parse import parse_qs, quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.schemas.decision import DecisionResponse, MarketData
from app.services.access_control import (
    ACCESS_COOKIE_NAME,
    has_access,
    is_access_enabled,
    require_access,
    validate_access_code,
)
from app.services.candle_data import fetch_candles
from app.services.decision_engine import build_decision
from app.services.db import get_storage_backend
from app.services.feed_engine import build_decision_feed
from app.services.feedback_service import (
    create_feedback_entry,
    get_feedback_summary,
    init_feedback_db,
    list_feedback_entries,
)
from app.services.i18n import (
    LANG_COOKIE_NAME,
    get_lang_from_request,
    normalize_lang,
    t,
)
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
    init_feedback_db()


def safe_next_path(next_path: str) -> str:
    if not next_path or not next_path.startswith("/") or next_path.startswith("//"):
        return "/"
    if "\n" in next_path or "\r" in next_path:
        return "/"

    return next_path


def language_switch_html(lang: str, path: str) -> str:
    safe_path = safe_next_path(path)
    next_param = quote(safe_path, safe="/")
    en_active = " active" if lang == "en" else ""
    ua_active = " active" if lang == "ua" else ""

    return f"""
            <div class="language-switch" aria-label="Language switch">
                <a class="lang-link{en_active}" href="/set-language/en?next={next_param}">EN</a>
                <a class="lang-link{ua_active}" href="/set-language/ua?next={next_param}">UA</a>
            </div>
    """


def render_html(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))

    return rendered


@app.get("/api")
def api_root():
    return {
        "product": "NOVAQ AI",
        "version": APP_VERSION,
        "status": "online",
        "message": "AI Decision Intelligence Layer is running",
        "dashboard": "/dashboard",
        "feed": "/feed",
        "feed_dashboard": "/feed-dashboard",
        "tracking_summary": "/tracking-summary",
        "tracked_signals": "/tracked-signals",
        "tracking_dashboard": "/tracking-dashboard",
        "evaluate_open_signals": "/evaluate-open-signals",
        "performance_analytics": "/performance-analytics",
        "performance_dashboard": "/performance-dashboard",
        "beta": "/beta",
        "feedback": "/feedback",
        "feedback_summary": "/api/feedback-summary",
        "admin_feedback": "/admin-feedback",
        "login": "/login",
        "logout": "/logout",
        "docs": "/docs",
        "health": "/health",
        "access_control": "enabled" if is_access_enabled() else "disabled",
        "storage_backend": get_storage_backend(),
        "languages": ["en", "ua"],
        "default_language": "en",
        "time_utc": datetime.now(timezone.utc).isoformat()
    }


@app.get("/set-language/{lang}")
def set_language(lang: str, next: str = "/"):
    normalized = normalize_lang(lang)
    response = RedirectResponse(url=safe_next_path(next), status_code=303)
    response.set_cookie(
        key=LANG_COOKIE_NAME,
        value=normalized,
        httponly=False,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
    )
    return response


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    lang = get_lang_from_request(request)
    return render_html("""
<!DOCTYPE html>
<html lang="en" translate="no">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="google" content="notranslate" />
    <title>NOVAQ AI Trading Intelligence</title>

    <style>
        * {
            box-sizing: border-box;
        }

        :root {
            --bg: #050810;
            --bg-soft: #09111f;
            --panel: rgba(14, 24, 42, 0.86);
            --panel-strong: rgba(17, 31, 55, 0.96);
            --line: rgba(255, 255, 255, 0.1);
            --line-bright: rgba(0, 255, 194, 0.24);
            --text: #f4f8ff;
            --muted: #91a0b8;
            --soft: #c9d5e8;
            --cyan: #00ffc2;
            --blue: #4b8dff;
            --deep-blue: #193c80;
        }

        html {
            min-height: 100%;
            background: var(--bg);
        }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: Arial, Helvetica, sans-serif;
            color: var(--text);
            background:
                linear-gradient(145deg, rgba(0, 255, 194, 0.11) 0%, transparent 31%),
                linear-gradient(215deg, rgba(75, 141, 255, 0.14) 0%, transparent 34%),
                linear-gradient(180deg, #050810 0%, #09111f 52%, #050810 100%);
        }

        a {
            color: inherit;
        }

        .page {
            width: min(1180px, calc(100% - 40px));
            margin: 0 auto;
            padding: 30px 0 34px;
        }

        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            margin-bottom: 64px;
        }

        .brand {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-size: 22px;
            font-weight: 950;
            letter-spacing: 0;
        }

        .brand-mark {
            width: 34px;
            height: 34px;
            display: grid;
            place-items: center;
            border: 1px solid var(--line-bright);
            border-radius: 8px;
            background: linear-gradient(135deg, rgba(0, 255, 194, 0.18), rgba(75, 141, 255, 0.18));
            color: var(--cyan);
            font-size: 15px;
        }

        .status {
            display: inline-flex;
            align-items: center;
            min-height: 34px;
            border: 1px solid var(--line-bright);
            border-radius: 8px;
            padding: 8px 12px;
            color: var(--cyan);
            background: rgba(0, 255, 194, 0.07);
            font-size: 12px;
            font-weight: 800;
            white-space: nowrap;
        }

        .top-actions,
        .language-switch {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
            justify-content: flex-end;
        }

        .language-switch {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 3px;
            background: rgba(255, 255, 255, 0.045);
        }

        .lang-link {
            min-width: 34px;
            border-radius: 7px;
            padding: 6px 8px;
            color: var(--muted);
            text-align: center;
            text-decoration: none;
            font-size: 12px;
            font-weight: 950;
        }

        .lang-link.active {
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
        }

        .hero {
            display: grid;
            grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
            gap: 26px;
            align-items: center;
            margin-bottom: 28px;
        }

        .hero-copy {
            min-width: 0;
        }

        .eyebrow {
            margin: 0 0 18px;
            color: var(--cyan);
            font-size: 12px;
            font-weight: 900;
            letter-spacing: 0;
            text-transform: uppercase;
        }

        h1 {
            max-width: 780px;
            margin: 0;
            font-size: clamp(42px, 7vw, 76px);
            line-height: 0.96;
            letter-spacing: 0;
            font-weight: 950;
        }

        .subtitle {
            max-width: 740px;
            margin: 22px 0 0;
            color: var(--soft);
            font-size: 18px;
            line-height: 1.65;
        }

        .disclaimer {
            max-width: 720px;
            margin: 20px 0 0;
            color: var(--muted);
            font-size: 13px;
            line-height: 1.55;
        }

        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 30px;
        }

        .button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 46px;
            border-radius: 8px;
            padding: 13px 16px;
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            text-decoration: none;
            font-size: 14px;
            font-weight: 950;
            box-shadow: 0 14px 34px rgba(0, 255, 194, 0.12);
        }

        .button.secondary {
            color: var(--text);
            background: rgba(255, 255, 255, 0.055);
            border: 1px solid var(--line);
            box-shadow: none;
        }

        .button:hover {
            filter: brightness(1.08);
        }

        .terminal {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: linear-gradient(180deg, rgba(17, 31, 55, 0.94), rgba(9, 17, 31, 0.96));
            box-shadow: 0 26px 70px rgba(0, 0, 0, 0.34);
            overflow: hidden;
        }

        .terminal-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            border-bottom: 1px solid var(--line);
            padding: 14px 16px;
            color: var(--muted);
            font-size: 12px;
            font-weight: 800;
        }

        .pulse {
            color: var(--cyan);
        }

        .terminal-body {
            display: grid;
            gap: 12px;
            padding: 16px;
        }

        .signal-row {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 14px;
            align-items: center;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 13px;
            background: rgba(255, 255, 255, 0.035);
        }

        .signal-label {
            color: var(--muted);
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
        }

        .signal-value {
            margin-top: 6px;
            color: var(--text);
            font-size: 18px;
            font-weight: 950;
        }

        .chip {
            border-radius: 8px;
            padding: 7px 9px;
            background: rgba(0, 255, 194, 0.1);
            color: var(--cyan);
            font-size: 12px;
            font-weight: 900;
            white-space: nowrap;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin-top: 28px;
        }

        .card {
            min-height: 126px;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 17px;
            background: var(--panel);
        }

        .card h2,
        .card h3 {
            margin: 0;
            font-size: 16px;
            line-height: 1.25;
            letter-spacing: 0;
        }

        .card p {
            margin: 12px 0 0;
            color: var(--muted);
            font-size: 13px;
            line-height: 1.5;
        }

        .section {
            margin-top: 36px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel-strong);
            padding: 22px;
        }

        .section-head {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 18px;
            margin-bottom: 18px;
        }

        .section h2 {
            margin: 0;
            font-size: 26px;
            letter-spacing: 0;
        }

        .section-note {
            margin: 0;
            max-width: 430px;
            color: var(--muted);
            font-size: 13px;
            line-height: 1.5;
            text-align: right;
        }

        .insight-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
        }

        .insight {
            min-height: 58px;
            display: flex;
            align-items: center;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 12px 13px;
            background: rgba(255, 255, 255, 0.04);
            color: var(--soft);
            font-size: 14px;
            font-weight: 850;
        }

        footer {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            margin-top: 28px;
            padding-top: 20px;
            border-top: 1px solid var(--line);
            color: #738197;
            font-size: 12px;
            line-height: 1.5;
        }

        @media (max-width: 960px) {
            .topbar {
                margin-bottom: 40px;
            }

            .hero,
            .grid,
            .insight-grid {
                grid-template-columns: 1fr 1fr;
            }

            .hero-copy {
                grid-column: 1 / -1;
            }

            .terminal {
                grid-column: 1 / -1;
            }
        }

        @media (max-width: 680px) {
            .page {
                width: min(100% - 24px, 1180px);
                padding-top: 22px;
            }

            .topbar,
            .top-actions,
            .section-head,
            footer {
                align-items: flex-start;
                flex-direction: column;
            }

            .hero,
            .grid,
            .insight-grid {
                grid-template-columns: 1fr;
            }

            h1 {
                font-size: 42px;
            }

            .subtitle {
                font-size: 16px;
            }

            .button {
                width: 100%;
            }

            .section {
                padding: 16px;
            }

            .section-note {
                text-align: left;
            }
        }
    </style>
</head>

<body>
    <main class="page">
        <header class="topbar">
            <div class="brand" aria-label="NOVAQ AI">
                <span class="brand-mark">NQ</span>
                <span>{{BRAND}}</span>
            </div>
            <div class="top-actions">
                {{LANG_SWITCH}}
                <div class="status">{{SYSTEM_ONLINE}}</div>
            </div>
        </header>

        <section class="hero">
            <div class="hero-copy">
                <p class="eyebrow">AI Decision Intelligence Layer</p>
                <h1>{{HEADLINE_LANDING}}</h1>
                <p class="subtitle">
                    {{SUBTITLE_LANDING}}
                </p>
                <p class="disclaimer">
                    {{DISCLAIMER}}
                </p>
                <div class="actions" aria-label="Primary navigation">
                    <a class="button" href="/feed-dashboard">{{OPEN_DECISION_FEED}}</a>
                    <a class="button secondary" href="/beta">{{BETA_GUIDE}}</a>
                    <a class="button" href="/login">{{DEMO_LOGIN}}</a>
                    <a class="button secondary" href="/performance-dashboard">{{VIEW_ANALYTICS}}</a>
                    <a class="button secondary" href="/feedback">{{GIVE_FEEDBACK}}</a>
                    <a class="button secondary" href="/docs">{{API_DOCS}}</a>
                </div>
            </div>

            <aside class="terminal" aria-label="Decision intelligence preview">
                <div class="terminal-top">
                    <span>NOVAQ MARKET STATE</span>
                    <span class="pulse">LIVE</span>
                </div>
                <div class="terminal-body">
                    <div class="signal-row">
                        <div>
                            <div class="signal-label">Action</div>
                            <div class="signal-value">Risk-Filtered Signal</div>
                        </div>
                        <span class="chip">Decision Layer</span>
                    </div>
                    <div class="signal-row">
                        <div>
                            <div class="signal-label">Opportunity Score</div>
                            <div class="signal-value">Ranked Market Setup</div>
                        </div>
                        <span class="chip">Quality Logic</span>
                    </div>
                    <div class="signal-row">
                        <div>
                            <div class="signal-label">Performance</div>
                            <div class="signal-value">Paper Tracking Analytics</div>
                        </div>
                        <span class="chip">Evaluation</span>
                    </div>
                </div>
            </aside>
        </section>

        <section class="grid" aria-label="NOVAQ AI features">
            <article class="card">
                <h2>Live Market Data</h2>
                <p>Current crypto market inputs for decisions and dashboards.</p>
            </article>
            <article class="card">
                <h2>Market State Engine</h2>
                <p>Regime context for trend, risk, and trade readiness.</p>
            </article>
            <article class="card">
                <h2>Signal Engine</h2>
                <p>Structured signal quality across momentum and market inputs.</p>
            </article>
            <article class="card">
                <h2>Opportunity Score</h2>
                <p>Ranked setups for faster comparison across assets.</p>
            </article>
            <article class="card">
                <h2>Paper Signal Tracking</h2>
                <p>Track simulated decisions without touching user funds.</p>
            </article>
            <article class="card">
                <h2>Auto Evaluation</h2>
                <p>Evaluate open paper signals against outcome rules.</p>
            </article>
            <article class="card">
                <h2>Performance Analytics</h2>
                <p>Review closed signal behavior and decision quality.</p>
            </article>
            <article class="card">
                <h2>Risk-First Decisions</h2>
                <p>Show risk level, failure scenario, and safer alternatives.</p>
            </article>
        </section>

        <section class="section" aria-labelledby="shows-title">
            <div class="section-head">
                <h2 id="shows-title">What NOVAQ AI shows</h2>
                <p class="section-note">Decision outputs are built for clarity, comparison, and risk awareness.</p>
            </div>
            <div class="insight-grid">
                <div class="insight">Action</div>
                <div class="insight">Confidence</div>
                <div class="insight">Opportunity Score</div>
                <div class="insight">Risk Level</div>
                <div class="insight">Market State</div>
                <div class="insight">Reasoning</div>
                <div class="insight">Failure Scenario</div>
                <div class="insight">Safer Alternative</div>
            </div>
        </section>

        <footer>
            <div>NOVAQ AI v{{APP_VERSION}}</div>
            <div>Educational analytics only. Not financial advice. {{BETA_FOOTER_NOTE}}</div>
        </footer>
    </main>
</body>
</html>
    """, {
        "APP_VERSION": APP_VERSION,
        "BRAND": t(lang, "brand"),
        "LANG_SWITCH": language_switch_html(lang, "/"),
        "SYSTEM_ONLINE": t(lang, "system_online"),
        "HEADLINE_LANDING": t(lang, "headline_landing"),
        "SUBTITLE_LANDING": t(lang, "subtitle_landing"),
        "DISCLAIMER": t(lang, "disclaimer"),
        "OPEN_DECISION_FEED": t(lang, "open_decision_feed"),
        "BETA_GUIDE": t(lang, "beta_guide"),
        "DEMO_LOGIN": t(lang, "demo_login"),
        "VIEW_ANALYTICS": t(lang, "view_analytics"),
        "GIVE_FEEDBACK": t(lang, "give_feedback"),
        "API_DOCS": t(lang, "api_docs"),
        "BETA_FOOTER_NOTE": t(lang, "beta_footer_note"),
    })


@app.get("/beta", response_class=HTMLResponse)
def beta_onboarding(request: Request):
    lang = get_lang_from_request(request)
    return render_html("""
<!DOCTYPE html>
<html lang="en" translate="no">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="google" content="notranslate" />
    <title>NOVAQ AI Beta Guide</title>

    <style>
        * {
            box-sizing: border-box;
        }

        :root {
            --bg: #050810;
            --panel: rgba(14, 24, 42, 0.9);
            --panel-strong: rgba(17, 31, 55, 0.96);
            --line: rgba(255, 255, 255, 0.1);
            --line-bright: rgba(0, 255, 194, 0.24);
            --text: #f4f8ff;
            --muted: #91a0b8;
            --soft: #c9d5e8;
            --cyan: #00ffc2;
            --blue: #4b8dff;
            --amber: #ffd166;
        }

        html {
            min-height: 100%;
            background: var(--bg);
        }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: Arial, Helvetica, sans-serif;
            color: var(--text);
            background:
                linear-gradient(145deg, rgba(0, 255, 194, 0.11), transparent 34%),
                linear-gradient(215deg, rgba(75, 141, 255, 0.14), transparent 36%),
                linear-gradient(180deg, #050810 0%, #09111f 52%, #050810 100%);
        }

        .page {
            width: min(1180px, calc(100% - 40px));
            margin: 0 auto;
            padding: 30px 0 42px;
        }

        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            margin-bottom: 56px;
        }

        .brand-wrap {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }

        .brand {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-size: 22px;
            font-weight: 950;
            letter-spacing: 0;
        }

        .brand-mark {
            width: 34px;
            height: 34px;
            display: grid;
            place-items: center;
            border: 1px solid var(--line-bright);
            border-radius: 8px;
            background: linear-gradient(135deg, rgba(0, 255, 194, 0.18), rgba(75, 141, 255, 0.18));
            color: var(--cyan);
            font-size: 15px;
        }

        .badge {
            border: 1px solid rgba(0, 255, 194, 0.28);
            border-radius: 8px;
            padding: 8px 10px;
            color: var(--cyan);
            background: rgba(0, 255, 194, 0.08);
            font-size: 12px;
            font-weight: 900;
            white-space: nowrap;
        }

        .nav {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: flex-end;
        }

        .language-switch {
            display: flex;
            align-items: center;
            gap: 4px;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 3px;
            background: rgba(255, 255, 255, 0.045);
        }

        .lang-link {
            min-width: 34px;
            border-radius: 7px;
            padding: 6px 8px;
            color: var(--muted);
            text-align: center;
            text-decoration: none;
            font-size: 12px;
            font-weight: 950;
        }

        .lang-link.active {
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
        }

        .nav a,
        .cta a {
            border-radius: 8px;
            padding: 10px 12px;
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            text-decoration: none;
            font-size: 13px;
            font-weight: 950;
        }

        .nav a.secondary,
        .cta a.secondary {
            color: var(--text);
            background: rgba(255, 255, 255, 0.055);
            border: 1px solid var(--line);
        }

        .language-switch .lang-link {
            min-width: 34px;
            padding: 6px 8px;
            color: var(--muted);
            background: transparent;
            border: 0;
        }

        .language-switch .lang-link.active {
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
        }

        .hero {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(280px, 420px);
            gap: 22px;
            align-items: stretch;
            margin-bottom: 28px;
        }

        h1 {
            max-width: 780px;
            margin: 0;
            font-size: clamp(42px, 7vw, 76px);
            line-height: 0.96;
            letter-spacing: 0;
            font-weight: 950;
        }

        .subtitle {
            max-width: 760px;
            margin: 20px 0 0;
            color: var(--soft);
            font-size: 18px;
            line-height: 1.65;
        }

        .disclaimer-box {
            align-self: end;
            border: 1px solid var(--line-bright);
            border-radius: 8px;
            padding: 18px;
            background: rgba(0, 255, 194, 0.07);
            color: var(--soft);
            line-height: 1.55;
            font-size: 14px;
        }

        .section {
            margin-top: 22px;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 22px;
            background: var(--panel);
        }

        .section h2 {
            margin: 0;
            font-size: 26px;
            line-height: 1.15;
            letter-spacing: 0;
        }

        .section > p {
            margin: 14px 0 0;
            color: var(--soft);
            line-height: 1.65;
        }

        .steps,
        .decision-grid,
        .feedback-grid,
        .limits-grid {
            display: grid;
            gap: 12px;
            margin-top: 18px;
        }

        .steps {
            grid-template-columns: repeat(5, minmax(0, 1fr));
        }

        .decision-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .feedback-grid,
        .limits-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .card {
            min-height: 128px;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 16px;
            background: rgba(255, 255, 255, 0.04);
        }

        .step-number {
            width: 30px;
            height: 30px;
            display: grid;
            place-items: center;
            border-radius: 8px;
            margin-bottom: 12px;
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            font-weight: 950;
        }

        .card h3 {
            margin: 0;
            color: var(--text);
            font-size: 16px;
            line-height: 1.25;
            letter-spacing: 0;
        }

        .card p {
            margin: 10px 0 0;
            color: var(--muted);
            line-height: 1.5;
            font-size: 13px;
        }

        .decision-card {
            min-height: 150px;
        }

        .field-name {
            display: block;
            color: var(--cyan);
            font-size: 12px;
            font-weight: 950;
            text-transform: uppercase;
        }

        .cta {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 18px;
        }

        footer {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            margin-top: 28px;
            padding-top: 20px;
            border-top: 1px solid var(--line);
            color: #738197;
            font-size: 12px;
            line-height: 1.5;
        }

        @media (max-width: 1040px) {
            .steps,
            .decision-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .feedback-grid,
            .limits-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 760px) {
            .page {
                width: min(100% - 24px, 1180px);
                padding-top: 22px;
            }

            .topbar,
            footer {
                align-items: flex-start;
                flex-direction: column;
            }

            .nav {
                justify-content: flex-start;
            }

            .hero,
            .steps,
            .decision-grid,
            .feedback-grid,
            .limits-grid {
                grid-template-columns: 1fr;
            }

            h1 {
                font-size: 42px;
            }

            .cta a,
            .nav a {
                width: 100%;
                text-align: center;
            }
        }
    </style>
</head>

<body>
    <main class="page">
        <header class="topbar">
            <div class="brand-wrap">
                <div class="brand" aria-label="NOVAQ AI">
                    <span class="brand-mark">NQ</span>
                    <span>{{BRAND}}</span>
                </div>
                <span class="badge">{{BETA_BADGE}}</span>
            </div>
            <nav class="nav" aria-label="Beta guide navigation">
                {{LANG_SWITCH}}
                <a href="/">{{HOME}}</a>
                <a href="/feed-dashboard">{{DECISION_FEED}}</a>
                <a class="secondary" href="/feedback">{{FEEDBACK}}</a>
                <a class="secondary" href="/docs">{{API_DOCS}}</a>
            </nav>
        </header>

        <section class="hero">
            <div>
                <h1>{{START_TESTING}}</h1>
                <p class="subtitle">{{BETA_SUBTITLE}}</p>
            </div>
            <aside class="disclaimer-box">
                {{DISCLAIMER}}
            </aside>
        </section>

        <section class="section">
            <h2>{{WHAT_IS_NOVAQ}}</h2>
            <p>{{WHAT_IS_NOVAQ_TEXT}}</p>
        </section>

        <section class="section">
            <h2>{{HOW_TO_TEST}}</h2>
            <div class="steps">
                <article class="card">
                    <div class="step-number">1</div>
                    <h3>{{OPEN_DECISION_FEED_STEP}}</h3>
                    <p>{{OPEN_DECISION_FEED_STEP_TEXT}}</p>
                </article>
                <article class="card">
                    <div class="step-number">2</div>
                    <h3>{{PICK_ASSETS}}</h3>
                    <p>{{PICK_ASSETS_TEXT}}</p>
                </article>
                <article class="card">
                    <div class="step-number">3</div>
                    <h3>{{READ_THE_SCORE}}</h3>
                    <p>{{READ_THE_SCORE_TEXT}}</p>
                </article>
                <article class="card">
                    <div class="step-number">4</div>
                    <h3>{{DO_NOT_TRADE_BLINDLY}}</h3>
                    <p>{{DO_NOT_TRADE_BLINDLY_TEXT}}</p>
                </article>
                <article class="card">
                    <div class="step-number">5</div>
                    <h3>{{SEND_FEEDBACK}}</h3>
                    <p>{{SEND_FEEDBACK_STEP_TEXT}}</p>
                </article>
            </div>
        </section>

        <section class="section">
            <h2>{{HOW_TO_READ_DECISION}}</h2>
            <div class="decision-grid">
                <article class="card decision-card">
                    <span class="field-name">{{ACTION}}</span>
                    <p>{{ACTION_TEXT}}</p>
                </article>
                <article class="card decision-card">
                    <span class="field-name">{{CONFIDENCE}}</span>
                    <p>{{CONFIDENCE_TEXT}}</p>
                </article>
                <article class="card decision-card">
                    <span class="field-name">{{OPPORTUNITY_SCORE}}</span>
                    <p>{{OPPORTUNITY_SCORE_TEXT}}</p>
                </article>
                <article class="card decision-card">
                    <span class="field-name">{{RISK_LEVEL}}</span>
                    <p>{{RISK_LEVEL_TEXT}}</p>
                </article>
                <article class="card decision-card">
                    <span class="field-name">{{MARKET_STATE}}</span>
                    <p>{{MARKET_STATE_TEXT}}</p>
                </article>
                <article class="card decision-card">
                    <span class="field-name">{{REASONING}}</span>
                    <p>{{REASONING_TEXT}}</p>
                </article>
                <article class="card decision-card">
                    <span class="field-name">{{FAILURE_SCENARIO}}</span>
                    <p>{{FAILURE_SCENARIO_TEXT}}</p>
                </article>
                <article class="card decision-card">
                    <span class="field-name">{{SAFER_ALTERNATIVE}}</span>
                    <p>{{SAFER_ALTERNATIVE_TEXT}}</p>
                </article>
            </div>
        </section>

        <section class="section">
            <h2>{{WHAT_FEEDBACK_WE_NEED}}</h2>
            <div class="feedback-grid">
                <article class="card"><h3>{{UNDERSTANDABILITY}}</h3><p>{{UNDERSTANDABILITY_TEXT}}</p></article>
                <article class="card"><h3>{{TRUST}}</h3><p>{{TRUST_TEXT}}</p></article>
                <article class="card"><h3>{{CONFUSION}}</h3><p>{{CONFUSION_TEXT}}</p></article>
                <article class="card"><h3>{{WORKFLOW_VALUE}}</h3><p>{{WORKFLOW_VALUE_TEXT}}</p></article>
                <article class="card"><h3>{{MISSING_FEATURE}}</h3><p>{{MISSING_FEATURE_TEXT}}</p></article>
                <article class="card"><h3>{{PRICING_SIGNAL}}</h3><p>{{PRICING_SIGNAL_TEXT}}</p></article>
            </div>
        </section>

        <section class="section">
            <h2>{{BETA_LIMITATIONS}}</h2>
            <div class="limits-grid">
                <article class="card"><h3>{{EDUCATIONAL_ONLY}}</h3><p>{{EDUCATIONAL_ONLY_TEXT}}</p></article>
                <article class="card"><h3>{{NO_EXECUTION}}</h3><p>{{NO_EXECUTION_TEXT}}</p></article>
                <article class="card"><h3>{{NO_FUNDS_ACCESS}}</h3><p>{{NO_FUNDS_ACCESS_TEXT}}</p></article>
                <article class="card"><h3>{{DATA_AVAILABILITY}}</h3><p>{{DATA_AVAILABILITY_TEXT}}</p></article>
                <article class="card"><h3>{{SAMPLE_SIZE}}</h3><p>{{SAMPLE_SIZE_TEXT}}</p></article>
                <article class="card"><h3>{{FAST_ITERATION}}</h3><p>{{FAST_ITERATION_TEXT}}</p></article>
            </div>
        </section>

        <section class="section">
            <h2>{{START_TESTING_SECTION}}</h2>
            <div class="cta">
                <a href="/feed-dashboard">{{OPEN_DECISION_FEED}}</a>
                <a href="/feedback">{{SEND_FEEDBACK}}</a>
                <a class="secondary" href="/login">{{DEMO_LOGIN}}</a>
                <a class="secondary" href="/docs">{{VIEW_API_DOCS}}</a>
            </div>
        </section>

        <footer>
            <div>NOVAQ AI {{BETA_GUIDE}}</div>
            <div>{{DISCLAIMER_SHORT}}</div>
        </footer>
    </main>
</body>
</html>
    """, {
        "BRAND": t(lang, "brand"),
        "BETA_BADGE": t(lang, "beta_badge"),
        "LANG_SWITCH": language_switch_html(lang, "/beta"),
        "HOME": t(lang, "home"),
        "DECISION_FEED": t(lang, "decision_feed"),
        "FEEDBACK": t(lang, "feedback"),
        "API_DOCS": t(lang, "api_docs"),
        "START_TESTING": t(lang, "start_testing"),
        "BETA_SUBTITLE": t(lang, "beta_subtitle"),
        "DISCLAIMER": t(lang, "disclaimer"),
        "WHAT_IS_NOVAQ": t(lang, "what_is_novaq"),
        "WHAT_IS_NOVAQ_TEXT": t(lang, "what_is_novaq_text"),
        "HOW_TO_TEST": t(lang, "how_to_test"),
        "OPEN_DECISION_FEED_STEP": t(lang, "open_decision_feed_step"),
        "OPEN_DECISION_FEED_STEP_TEXT": t(lang, "open_decision_feed_step_text"),
        "PICK_ASSETS": t(lang, "pick_assets"),
        "PICK_ASSETS_TEXT": t(lang, "pick_assets_text"),
        "READ_THE_SCORE": t(lang, "read_the_score"),
        "READ_THE_SCORE_TEXT": t(lang, "read_the_score_text"),
        "DO_NOT_TRADE_BLINDLY": t(lang, "do_not_trade_blindly"),
        "DO_NOT_TRADE_BLINDLY_TEXT": t(lang, "do_not_trade_blindly_text"),
        "SEND_FEEDBACK": t(lang, "send_feedback"),
        "SEND_FEEDBACK_STEP_TEXT": t(lang, "send_feedback_step_text"),
        "HOW_TO_READ_DECISION": t(lang, "how_to_read_decision"),
        "ACTION": t(lang, "action"),
        "ACTION_TEXT": t(lang, "action_text"),
        "CONFIDENCE": t(lang, "confidence"),
        "CONFIDENCE_TEXT": t(lang, "confidence_text"),
        "OPPORTUNITY_SCORE": t(lang, "opportunity_score"),
        "OPPORTUNITY_SCORE_TEXT": t(lang, "opportunity_score_text"),
        "RISK_LEVEL": t(lang, "risk_level"),
        "RISK_LEVEL_TEXT": t(lang, "risk_level_text"),
        "MARKET_STATE": t(lang, "market_state"),
        "MARKET_STATE_TEXT": t(lang, "market_state_text"),
        "REASONING": t(lang, "reasoning"),
        "REASONING_TEXT": t(lang, "reasoning_text"),
        "FAILURE_SCENARIO": t(lang, "failure_scenario"),
        "FAILURE_SCENARIO_TEXT": t(lang, "failure_scenario_text"),
        "SAFER_ALTERNATIVE": t(lang, "safer_alternative"),
        "SAFER_ALTERNATIVE_TEXT": t(lang, "safer_alternative_text"),
        "WHAT_FEEDBACK_WE_NEED": t(lang, "what_feedback_we_need"),
        "UNDERSTANDABILITY": t(lang, "understandability"),
        "UNDERSTANDABILITY_TEXT": t(lang, "understandability_text"),
        "TRUST": t(lang, "trust"),
        "TRUST_TEXT": t(lang, "trust_text"),
        "CONFUSION": t(lang, "confusion"),
        "CONFUSION_TEXT": t(lang, "confusion_text"),
        "WORKFLOW_VALUE": t(lang, "workflow_value"),
        "WORKFLOW_VALUE_TEXT": t(lang, "workflow_value_text"),
        "MISSING_FEATURE": t(lang, "missing_feature"),
        "MISSING_FEATURE_TEXT": t(lang, "missing_feature_text"),
        "PRICING_SIGNAL": t(lang, "pricing_signal"),
        "PRICING_SIGNAL_TEXT": t(lang, "pricing_signal_text"),
        "BETA_LIMITATIONS": t(lang, "beta_limitations"),
        "EDUCATIONAL_ONLY": t(lang, "educational_only"),
        "EDUCATIONAL_ONLY_TEXT": t(lang, "educational_only_text"),
        "NO_EXECUTION": t(lang, "no_execution"),
        "NO_EXECUTION_TEXT": t(lang, "no_execution_text"),
        "NO_FUNDS_ACCESS": t(lang, "no_funds_access"),
        "NO_FUNDS_ACCESS_TEXT": t(lang, "no_funds_access_text"),
        "DATA_AVAILABILITY": t(lang, "data_availability"),
        "DATA_AVAILABILITY_TEXT": t(lang, "data_availability_text"),
        "SAMPLE_SIZE": t(lang, "sample_size"),
        "SAMPLE_SIZE_TEXT": t(lang, "sample_size_text"),
        "FAST_ITERATION": t(lang, "fast_iteration"),
        "FAST_ITERATION_TEXT": t(lang, "fast_iteration_text"),
        "START_TESTING_SECTION": t(lang, "start_testing_section"),
        "OPEN_DECISION_FEED": t(lang, "open_decision_feed"),
        "DEMO_LOGIN": t(lang, "demo_login"),
        "VIEW_API_DOCS": t(lang, "view_api_docs"),
        "BETA_GUIDE": t(lang, "beta_guide"),
        "DISCLAIMER_SHORT": "Educational analytics only. Not financial advice." if lang == "en" else "Лише освітня аналітика. Не фінансова порада.",
    })


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    lang = get_lang_from_request(request)
    error_block = ""
    if request.query_params.get("error") == "1":
        error_block = f'<div class="error">{t(lang, "invalid_access_code")}</div>'

    return render_html("""
<!DOCTYPE html>
<html lang="en" translate="no">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="google" content="notranslate" />
    <title>NOVAQ AI Demo Access</title>

    <style>
        * { box-sizing: border-box; }

        :root {
            --bg: #050810;
            --panel: rgba(14, 24, 42, 0.92);
            --line: rgba(255, 255, 255, 0.1);
            --line-bright: rgba(0, 255, 194, 0.24);
            --text: #f4f8ff;
            --muted: #91a0b8;
            --cyan: #00ffc2;
            --blue: #4b8dff;
            --red: #ff5c7a;
        }

        html {
            min-height: 100%;
            background: var(--bg);
        }

        body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 24px;
            font-family: Arial, Helvetica, sans-serif;
            color: var(--text);
            background:
                linear-gradient(145deg, rgba(0, 255, 194, 0.12), transparent 34%),
                linear-gradient(215deg, rgba(75, 141, 255, 0.15), transparent 36%),
                linear-gradient(180deg, #050810 0%, #09111f 52%, #050810 100%);
        }

        .shell {
            width: min(460px, 100%);
        }

        .brand {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 18px;
            font-size: 22px;
            font-weight: 950;
        }

        .top-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 18px;
        }

        .language-switch {
            display: flex;
            align-items: center;
            gap: 4px;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 3px;
            background: rgba(255, 255, 255, 0.045);
        }

        .lang-link {
            min-width: 34px;
            border-radius: 7px;
            padding: 6px 8px;
            color: var(--muted);
            text-align: center;
            text-decoration: none;
            font-size: 12px;
            font-weight: 950;
        }

        .lang-link.active {
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
        }

        .brand-mark {
            width: 34px;
            height: 34px;
            display: grid;
            place-items: center;
            border: 1px solid var(--line-bright);
            border-radius: 8px;
            background: linear-gradient(135deg, rgba(0, 255, 194, 0.18), rgba(75, 141, 255, 0.18));
            color: var(--cyan);
            font-size: 15px;
        }

        .panel {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 24px;
            background: var(--panel);
            box-shadow: 0 26px 70px rgba(0, 0, 0, 0.34);
        }

        h1 {
            margin: 0;
            font-size: 32px;
            line-height: 1.08;
            letter-spacing: 0;
        }

        .subtitle {
            margin: 10px 0 22px;
            color: var(--muted);
            line-height: 1.5;
        }

        form {
            display: grid;
            gap: 12px;
        }

        input {
            width: 100%;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px 15px;
            background: rgba(255, 255, 255, 0.055);
            color: var(--text);
            font-size: 15px;
            outline: none;
        }

        input:focus {
            border-color: var(--line-bright);
        }

        button,
        .link-button {
            min-height: 46px;
            border: 0;
            border-radius: 8px;
            padding: 13px 16px;
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            cursor: pointer;
            font-size: 14px;
            font-weight: 950;
            text-decoration: none;
            text-align: center;
        }

        .secondary-row {
            display: flex;
            gap: 10px;
            margin-top: 12px;
        }

        .secondary-row .link-button {
            flex: 1;
            color: var(--text);
            background: rgba(255, 255, 255, 0.055);
            border: 1px solid var(--line);
        }

        .error {
            margin-bottom: 14px;
            border: 1px solid rgba(255, 92, 122, 0.35);
            border-radius: 8px;
            padding: 10px 12px;
            background: rgba(255, 92, 122, 0.1);
            color: var(--red);
            font-size: 13px;
            font-weight: 800;
        }

        .disclaimer {
            margin: 16px 0 0;
            color: #738197;
            font-size: 12px;
            line-height: 1.5;
        }
    </style>
</head>

<body>
    <main class="shell">
        <div class="top-row">
            <div class="brand" aria-label="NOVAQ AI">
                <span class="brand-mark">NQ</span>
                <span>{{BRAND}}</span>
            </div>
            {{LANG_SWITCH}}
        </div>

        <section class="panel">
            <h1>{{PROTECTED_DEMO_ACCESS}}</h1>
            <p class="subtitle">{{LOGIN_SUBTITLE}}</p>
            {{ERROR_BLOCK}}
            <form method="post" action="/login?lang={{LANG}}">
                <input type="password" name="access_code" placeholder="Enter access code" autocomplete="current-password" required />
                <button type="submit">{{UNLOCK_DEMO}}</button>
            </form>
            <div class="secondary-row">
                <a class="link-button" href="/feed-dashboard">{{DECISION_FEED}}</a>
                <a class="link-button" href="/">{{HOME}}</a>
            </div>
            <p class="disclaimer">{{ACCESS_REQUIRED_NOTE}}</p>
        </section>
    </main>
</body>
</html>
    """, {
        "LANG": lang,
        "BRAND": t(lang, "brand"),
        "LANG_SWITCH": language_switch_html(lang, "/login"),
        "PROTECTED_DEMO_ACCESS": t(lang, "protected_demo_access"),
        "LOGIN_SUBTITLE": t(lang, "login_subtitle"),
        "ERROR_BLOCK": error_block,
        "UNLOCK_DEMO": t(lang, "unlock_demo"),
        "DECISION_FEED": t(lang, "decision_feed"),
        "HOME": t(lang, "home"),
        "ACCESS_REQUIRED_NOTE": t(lang, "access_required_note"),
    })


@app.post("/login")
async def login_submit(request: Request):
    lang = get_lang_from_request(request)
    body = await request.body()
    form_data = parse_qs(body.decode("utf-8"))
    access_code = form_data.get("access_code", [""])[0]

    if validate_access_code(access_code):
        response = RedirectResponse(url="/tracking-dashboard", status_code=303)
        response.set_cookie(
            key=ACCESS_COOKIE_NAME,
            value=access_code,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,
        )
        return response

    return RedirectResponse(url=f"/login?error=1&lang={lang}", status_code=303)


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(ACCESS_COOKIE_NAME)
    return response


@app.get("/feedback", response_class=HTMLResponse)
def feedback_page(request: Request):
    lang = get_lang_from_request(request)
    return render_html("""
<!DOCTYPE html>
<html lang="en" translate="no">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="google" content="notranslate" />
    <title>NOVAQ AI Beta Feedback</title>

    <style>
        * { box-sizing: border-box; }

        :root {
            --bg: #050810;
            --panel: rgba(14, 24, 42, 0.9);
            --panel-strong: rgba(17, 31, 55, 0.96);
            --line: rgba(255, 255, 255, 0.1);
            --line-bright: rgba(0, 255, 194, 0.24);
            --text: #f4f8ff;
            --muted: #91a0b8;
            --soft: #c9d5e8;
            --cyan: #00ffc2;
            --blue: #4b8dff;
        }

        html {
            min-height: 100%;
            background: var(--bg);
        }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: Arial, Helvetica, sans-serif;
            color: var(--text);
            background:
                linear-gradient(145deg, rgba(0, 255, 194, 0.11), transparent 34%),
                linear-gradient(215deg, rgba(75, 141, 255, 0.14), transparent 36%),
                linear-gradient(180deg, #050810 0%, #09111f 52%, #050810 100%);
        }

        .page {
            width: min(980px, calc(100% - 40px));
            margin: 0 auto;
            padding: 32px 0 42px;
        }

        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            margin-bottom: 30px;
        }

        .brand {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-size: 22px;
            font-weight: 950;
        }

        .brand-mark {
            width: 34px;
            height: 34px;
            display: grid;
            place-items: center;
            border: 1px solid var(--line-bright);
            border-radius: 8px;
            background: linear-gradient(135deg, rgba(0, 255, 194, 0.18), rgba(75, 141, 255, 0.18));
            color: var(--cyan);
            font-size: 15px;
        }

        .nav {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: flex-end;
        }

        .language-switch {
            display: flex;
            align-items: center;
            gap: 4px;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 3px;
            background: rgba(255, 255, 255, 0.045);
        }

        .lang-link {
            min-width: 34px;
            border-radius: 7px;
            padding: 6px 8px;
            color: var(--muted);
            text-align: center;
            text-decoration: none;
            font-size: 12px;
            font-weight: 950;
        }

        .lang-link.active {
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
        }

        .nav a,
        button {
            border: 0;
            border-radius: 8px;
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            cursor: pointer;
            font-size: 13px;
            font-weight: 950;
            text-decoration: none;
        }

        .nav a {
            padding: 10px 12px;
        }

        .language-switch .lang-link {
            min-width: 34px;
            padding: 6px 8px;
            color: var(--muted);
            background: transparent;
            border: 0;
        }

        .language-switch .lang-link.active {
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
        }

        .hero {
            margin-bottom: 20px;
        }

        h1 {
            max-width: 760px;
            margin: 0;
            font-size: clamp(38px, 6vw, 60px);
            line-height: 1;
            letter-spacing: 0;
        }

        .subtitle {
            max-width: 720px;
            margin: 16px 0 0;
            color: var(--soft);
            font-size: 18px;
            line-height: 1.6;
        }

        .disclaimer {
            margin: 12px 0 0;
            color: var(--muted);
            font-size: 13px;
        }

        .panel {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 20px;
            background: var(--panel);
            box-shadow: 0 26px 70px rgba(0, 0, 0, 0.28);
        }

        form {
            display: grid;
            gap: 14px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
        }

        label {
            display: grid;
            gap: 8px;
            color: var(--soft);
            font-size: 13px;
            font-weight: 850;
        }

        input,
        select,
        textarea {
            width: 100%;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 13px 14px;
            background: rgba(255, 255, 255, 0.055);
            color: var(--text);
            font-size: 14px;
            outline: none;
        }

        select option {
            color: #06101d;
        }

        textarea {
            min-height: 108px;
            resize: vertical;
        }

        input:focus,
        select:focus,
        textarea:focus {
            border-color: var(--line-bright);
        }

        .full {
            grid-column: 1 / -1;
        }

        button {
            width: fit-content;
            min-height: 48px;
            padding: 14px 18px;
        }

        @media (max-width: 760px) {
            .page {
                width: min(100% - 24px, 980px);
                padding-top: 22px;
            }

            .topbar {
                align-items: flex-start;
                flex-direction: column;
            }

            .nav {
                justify-content: flex-start;
            }

            .grid {
                grid-template-columns: 1fr;
            }

            button {
                width: 100%;
            }
        }
    </style>
</head>

<body>
    <main class="page">
        <header class="topbar">
            <div class="brand" aria-label="NOVAQ AI">
                <span class="brand-mark">NQ</span>
                <span>{{BRAND}}</span>
            </div>
            <nav class="nav" aria-label="Feedback navigation">
                {{LANG_SWITCH}}
                <a href="/">{{HOME}}</a>
                <a href="/feed-dashboard">{{DECISION_FEED}}</a>
                <a href="/docs">{{API_DOCS}}</a>
            </nav>
        </header>

        <section class="hero">
            <h1>{{FEEDBACK_TITLE}}</h1>
            <p class="subtitle">{{FEEDBACK_SUBTITLE}}</p>
            <p class="disclaimer">{{DISCLAIMER_SHORT}}</p>
        </section>

        <section class="panel">
            <form method="post" action="/feedback?lang={{LANG}}">
                <div class="grid">
                    <label>
                        {{NAME}}
                        <input type="text" name="name" autocomplete="name" />
                    </label>
                    <label>
                        {{CONTACT}}
                        <input type="text" name="contact" autocomplete="email" />
                    </label>
                    <label>
                        {{EXPERIENCE_LEVEL}}
                        <select name="experience_level">
                            <option value="">Select one</option>
                            <option>Beginner</option>
                            <option>Intermediate</option>
                            <option>Advanced</option>
                            <option>Professional</option>
                        </select>
                    </label>
                    <label>
                        {{MAIN_USE_CASE}}
                        <select name="main_use_case">
                            <option value="">Select one</option>
                            <option>Learn trading</option>
                            <option>Check market decisions</option>
                            <option>Validate signals</option>
                            <option>Paper trading</option>
                            <option>Analytics/research</option>
                            <option>Other</option>
                        </select>
                    </label>
                    <label>
                        {{CLARITY_RATING}}
                        <select name="clarity_rating">
                            <option value="0">Select 1-5</option>
                            <option value="1">1</option>
                            <option value="2">2</option>
                            <option value="3">3</option>
                            <option value="4">4</option>
                            <option value="5">5</option>
                        </select>
                    </label>
                    <label>
                        {{TRUST_RATING}}
                        <select name="trust_rating">
                            <option value="0">Select 1-5</option>
                            <option value="1">1</option>
                            <option value="2">2</option>
                            <option value="3">3</option>
                            <option value="4">4</option>
                            <option value="5">5</option>
                        </select>
                    </label>
                    <label>
                        {{WOULD_PAY}}
                        <select name="would_pay">
                            <option value="">Select one</option>
                            <option value="yes">yes</option>
                            <option value="no">no</option>
                            <option value="maybe">maybe</option>
                        </select>
                    </label>
                    <label>
                        {{PRICE_PREFERENCE}}
                        <select name="price_preference">
                            <option value="">Select one</option>
                            <option>Free only</option>
                            <option>$9/month</option>
                            <option>$19/month</option>
                            <option>$49/month</option>
                            <option>$99/month</option>
                            <option>B2B/API</option>
                        </select>
                    </label>
                    <label class="full">
                        {{LIKED}}
                        <textarea name="liked"></textarea>
                    </label>
                    <label class="full">
                        {{CONFUSING}}
                        <textarea name="confusing"></textarea>
                    </label>
                    <label class="full">
                        {{MISSING_FEATURES}}
                        <textarea name="missing_features"></textarea>
                    </label>
                    <label class="full">
                        {{GENERAL_FEEDBACK}}
                        <textarea name="general_feedback"></textarea>
                    </label>
                </div>
                <button type="submit">{{SEND_FEEDBACK}}</button>
            </form>
        </section>
    </main>
</body>
</html>
    """, {
        "LANG": lang,
        "BRAND": t(lang, "brand"),
        "LANG_SWITCH": language_switch_html(lang, "/feedback"),
        "HOME": t(lang, "home"),
        "DECISION_FEED": t(lang, "decision_feed"),
        "API_DOCS": t(lang, "api_docs"),
        "FEEDBACK_TITLE": t(lang, "feedback_title"),
        "FEEDBACK_SUBTITLE": t(lang, "feedback_subtitle"),
        "DISCLAIMER_SHORT": "Educational analytics only. Not financial advice." if lang == "en" else "Лише освітня аналітика. Не фінансова порада.",
        "NAME": t(lang, "name"),
        "CONTACT": t(lang, "contact"),
        "EXPERIENCE_LEVEL": t(lang, "experience_level"),
        "MAIN_USE_CASE": t(lang, "main_use_case"),
        "CLARITY_RATING": t(lang, "clarity_rating"),
        "TRUST_RATING": t(lang, "trust_rating"),
        "WOULD_PAY": t(lang, "would_pay"),
        "PRICE_PREFERENCE": t(lang, "price_preference"),
        "LIKED": t(lang, "liked"),
        "CONFUSING": t(lang, "confusing"),
        "MISSING_FEATURES": t(lang, "missing_features"),
        "GENERAL_FEEDBACK": t(lang, "general_feedback"),
        "SEND_FEEDBACK": t(lang, "send_feedback"),
    })


@app.post("/feedback", response_class=HTMLResponse)
async def submit_feedback(request: Request):
    lang = get_lang_from_request(request)
    body = await request.body()
    form_data = parse_qs(body.decode("utf-8"))

    def form_value(name: str, default: str = "") -> str:
        return form_data.get(name, [default])[0]

    create_feedback_entry(
        {
            "name": form_value("name"),
            "contact": form_value("contact"),
            "experience_level": form_value("experience_level"),
            "main_use_case": form_value("main_use_case"),
            "clarity_rating": form_value("clarity_rating", "0"),
            "trust_rating": form_value("trust_rating", "0"),
            "would_pay": form_value("would_pay"),
            "price_preference": form_value("price_preference"),
            "liked": form_value("liked"),
            "confusing": form_value("confusing"),
            "missing_features": form_value("missing_features"),
            "general_feedback": form_value("general_feedback"),
            "user_agent": request.headers.get("user-agent", ""),
        }
    )

    return render_html("""
<!DOCTYPE html>
<html lang="en" translate="no">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="google" content="notranslate" />
    <title>Thank you</title>

    <style>
        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 24px;
            font-family: Arial, Helvetica, sans-serif;
            color: #f4f8ff;
            background:
                linear-gradient(145deg, rgba(0, 255, 194, 0.12), transparent 34%),
                linear-gradient(215deg, rgba(75, 141, 255, 0.15), transparent 36%),
                linear-gradient(180deg, #050810 0%, #09111f 52%, #050810 100%);
        }

        .panel {
            width: min(520px, 100%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 26px;
            background: rgba(14, 24, 42, 0.92);
            box-shadow: 0 26px 70px rgba(0, 0, 0, 0.34);
        }

        .language-switch {
            display: flex;
            align-items: center;
            gap: 4px;
            width: fit-content;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 3px;
            margin-bottom: 18px;
            background: rgba(255, 255, 255, 0.045);
        }

        .lang-link {
            min-width: 34px;
            border-radius: 7px;
            padding: 6px 8px;
            color: #91a0b8;
            background: transparent;
            text-align: center;
            text-decoration: none;
            font-size: 12px;
            font-weight: 950;
        }

        .lang-link.active {
            color: #031018;
            background: linear-gradient(135deg, #00ffc2, #4b8dff);
        }

        h1 {
            margin: 0;
            font-size: 36px;
            letter-spacing: 0;
        }

        p {
            margin: 12px 0 22px;
            color: #c9d5e8;
            line-height: 1.6;
        }

        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        a {
            border-radius: 8px;
            padding: 13px 16px;
            color: #031018;
            background: linear-gradient(135deg, #00ffc2, #4b8dff);
            text-decoration: none;
            font-size: 14px;
            font-weight: 950;
        }

        a.secondary {
            color: #f4f8ff;
            background: rgba(255, 255, 255, 0.055);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .language-switch .lang-link {
            min-width: 34px;
            padding: 6px 8px;
            color: #91a0b8;
            background: transparent;
            border: 0;
        }

        .language-switch .lang-link.active {
            color: #031018;
            background: linear-gradient(135deg, #00ffc2, #4b8dff);
        }

        @media (max-width: 520px) {
            a {
                width: 100%;
                text-align: center;
            }
        }
    </style>
</head>

<body>
    <main class="panel">
        {{LANG_SWITCH}}
        <h1>{{THANK_YOU}}</h1>
        <p>{{THANK_YOU_TEXT}}</p>
        <div class="actions">
            <a href="/feed-dashboard">{{BACK_TO_DECISION_FEED}}</a>
            <a class="secondary" href="/">{{HOME}}</a>
        </div>
    </main>
</body>
</html>
    """, {
        "LANG_SWITCH": language_switch_html(lang, "/feedback"),
        "THANK_YOU": t(lang, "thank_you"),
        "THANK_YOU_TEXT": t(lang, "thank_you_text"),
        "BACK_TO_DECISION_FEED": t(lang, "back_to_decision_feed"),
        "HOME": t(lang, "home"),
    })


@app.get("/admin-feedback", response_class=HTMLResponse)
def admin_feedback(request: Request, limit: int = 100):
    if not has_access(request):
        return RedirectResponse(url="/login", status_code=303)

    summary = get_feedback_summary()
    feedback = list_feedback_entries(limit)

    def safe(value: object) -> str:
        if value is None:
            return ""
        return escape(str(value))

    cards = []
    for entry in feedback["entries"]:
        cards.append(
            f"""
            <article class="entry-card">
                <div class="entry-top">
                    <div><span class="label">ID</span><strong>{safe(entry.get("id"))}</strong></div>
                    <div><span class="label">Created UTC</span><strong>{safe(entry.get("created_at_utc"))}</strong></div>
                </div>
                <div class="meta-grid">
                    <div><span class="label">Name</span><strong>{safe(entry.get("name"))}</strong></div>
                    <div><span class="label">Contact</span><strong>{safe(entry.get("contact"))}</strong></div>
                    <div><span class="label">Experience</span><strong>{safe(entry.get("experience_level"))}</strong></div>
                    <div><span class="label">Use Case</span><strong>{safe(entry.get("main_use_case"))}</strong></div>
                    <div><span class="label">Clarity</span><strong>{safe(entry.get("clarity_rating"))}</strong></div>
                    <div><span class="label">Trust</span><strong>{safe(entry.get("trust_rating"))}</strong></div>
                    <div><span class="label">Would Pay</span><strong>{safe(entry.get("would_pay"))}</strong></div>
                    <div><span class="label">Price</span><strong>{safe(entry.get("price_preference"))}</strong></div>
                </div>
                <div class="text-grid">
                    <section><span class="label">Liked</span><p>{safe(entry.get("liked"))}</p></section>
                    <section><span class="label">Confusing</span><p>{safe(entry.get("confusing"))}</p></section>
                    <section><span class="label">Missing Features</span><p>{safe(entry.get("missing_features"))}</p></section>
                    <section><span class="label">General Feedback</span><p>{safe(entry.get("general_feedback"))}</p></section>
                </div>
            </article>
            """
        )

    entries_html = "\n".join(cards) if cards else '<div class="empty">No feedback yet.</div>'

    return f"""
<!DOCTYPE html>
<html lang="en" translate="no">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="google" content="notranslate" />
    <title>NOVAQ AI Feedback Admin</title>

    <style>
        * {{ box-sizing: border-box; }}

        :root {{
            --bg: #050810;
            --panel: rgba(14, 24, 42, 0.9);
            --panel-strong: rgba(17, 31, 55, 0.96);
            --line: rgba(255, 255, 255, 0.1);
            --text: #f4f8ff;
            --muted: #91a0b8;
            --soft: #c9d5e8;
            --cyan: #00ffc2;
            --blue: #4b8dff;
        }}

        body {{
            margin: 0;
            min-height: 100vh;
            font-family: Arial, Helvetica, sans-serif;
            color: var(--text);
            background:
                linear-gradient(145deg, rgba(0, 255, 194, 0.1), transparent 34%),
                linear-gradient(215deg, rgba(75, 141, 255, 0.12), transparent 36%),
                linear-gradient(180deg, #050810 0%, #09111f 52%, #050810 100%);
        }}

        .page {{
            width: min(1180px, calc(100% - 40px));
            margin: 0 auto;
            padding: 32px 0 42px;
        }}

        .header {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 20px;
            margin-bottom: 18px;
        }}

        h1 {{
            margin: 0;
            font-size: 34px;
            letter-spacing: 0;
        }}

        .subtitle {{
            margin-top: 8px;
            color: var(--muted);
        }}

        .nav {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 20px;
        }}

        .nav a {{
            border-radius: 8px;
            padding: 10px 12px;
            color: #031018;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            text-decoration: none;
            font-size: 12px;
            font-weight: 950;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 18px;
        }}

        .summary-card,
        .entry-card {{
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
        }}

        .summary-card {{
            min-height: 94px;
            padding: 15px;
        }}

        .summary-card strong {{
            display: block;
            margin-top: 8px;
            font-size: 26px;
        }}

        .label {{
            display: block;
            color: var(--muted);
            font-size: 11px;
            font-weight: 850;
            text-transform: uppercase;
        }}

        .entry-list {{
            display: grid;
            gap: 14px;
        }}

        .entry-card {{
            padding: 16px;
        }}

        .entry-top,
        .meta-grid,
        .text-grid {{
            display: grid;
            gap: 10px;
        }}

        .entry-top {{
            grid-template-columns: 120px minmax(0, 1fr);
            padding-bottom: 12px;
            border-bottom: 1px solid var(--line);
            margin-bottom: 12px;
        }}

        .meta-grid {{
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-bottom: 12px;
        }}

        .meta-grid div,
        .text-grid section {{
            min-width: 0;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 10px;
            background: rgba(255, 255, 255, 0.035);
        }}

        .meta-grid strong {{
            display: block;
            margin-top: 6px;
            color: var(--soft);
            word-break: break-word;
        }}

        .text-grid {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}

        p {{
            margin: 7px 0 0;
            color: var(--soft);
            line-height: 1.5;
            white-space: pre-wrap;
            word-break: break-word;
        }}

        .empty {{
            border: 1px dashed var(--line);
            border-radius: 8px;
            padding: 22px;
            color: var(--muted);
            text-align: center;
        }}

        @media (max-width: 980px) {{
            .summary,
            .meta-grid,
            .text-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
        }}

        @media (max-width: 640px) {{
            .page {{
                width: min(100% - 24px, 1180px);
            }}

            .header {{
                align-items: flex-start;
                flex-direction: column;
            }}

            .summary,
            .entry-top,
            .meta-grid,
            .text-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>

<body>
    <main class="page">
        <header class="header">
            <div>
                <h1>NOVAQ AI Feedback Admin</h1>
                <div class="subtitle">Beta user feedback and MVP signal quality notes</div>
            </div>
        </header>

        <nav class="nav" aria-label="Admin feedback navigation">
            <a href="/">Home</a>
            <a href="/feed-dashboard">Decision Feed</a>
            <a href="/tracking-dashboard">Tracking</a>
            <a href="/performance-dashboard">Performance</a>
            <a href="/logout">Logout</a>
        </nav>

        <section class="summary">
            <article class="summary-card"><span class="label">Total</span><strong>{safe(summary["total"])}</strong></article>
            <article class="summary-card"><span class="label">Avg Clarity</span><strong>{safe(summary["average_clarity_rating"])}</strong></article>
            <article class="summary-card"><span class="label">Avg Trust</span><strong>{safe(summary["average_trust_rating"])}</strong></article>
            <article class="summary-card"><span class="label">Would Pay Yes</span><strong>{safe(summary["would_pay_yes"])}</strong></article>
            <article class="summary-card"><span class="label">Would Pay Maybe</span><strong>{safe(summary["would_pay_maybe"])}</strong></article>
            <article class="summary-card"><span class="label">Would Pay No</span><strong>{safe(summary["would_pay_no"])}</strong></article>
        </section>

        <section class="entry-list">
            {entries_html}
        </section>
    </main>
</body>
</html>
    """


@app.get("/api/feedback-summary")
def api_feedback_summary(request: Request):
    require_access(request)
    return get_feedback_summary()


@app.get("/api/feedback")
def api_feedback(request: Request, limit: int = 100):
    require_access(request)
    return list_feedback_entries(limit)


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
def create_tracked_signal(request: Request, symbol: str):
    require_access(request)
    return track_signal(symbol)


@app.get("/track/{symbol}")
def create_tracked_signal_get(request: Request, symbol: str):
    require_access(request)
    return track_signal(symbol)


@app.get("/tracked-signals")
def get_tracked_signals(request: Request, status: str | None = None, limit: int = 50):
    require_access(request)
    return list_tracked_signals(status, limit)


@app.post("/tracked-signals/{signal_id}/close")
def close_tracked_signal(request: Request, signal_id: int, close_reason: str = "MANUAL_CLOSE"):
    require_access(request)
    return close_signal(signal_id, close_reason)


@app.get("/tracking-summary")
def tracking_summary(request: Request):
    require_access(request)
    return get_tracking_summary()


@app.post("/evaluate-open-signals")
def evaluate_open_signals_endpoint(
    request: Request,
    take_profit_percent: float = 1.0,
    stop_loss_percent: float = -0.7,
    max_age_minutes: int = 60,
    limit: int = 100
):
    require_access(request)
    return evaluate_open_signals(
        take_profit_percent=take_profit_percent,
        stop_loss_percent=stop_loss_percent,
        max_age_minutes=max_age_minutes,
        limit=limit
    )


@app.get("/evaluate-open-signals")
def evaluate_open_signals_get(
    request: Request,
    take_profit_percent: float = 1.0,
    stop_loss_percent: float = -0.7,
    max_age_minutes: int = 60,
    limit: int = 100
):
    require_access(request)
    return evaluate_open_signals(
        take_profit_percent=take_profit_percent,
        stop_loss_percent=stop_loss_percent,
        max_age_minutes=max_age_minutes,
        limit=limit
    )


@app.get("/performance-analytics")
def performance_analytics(request: Request, limit: int = 1000):
    require_access(request)
    return build_performance_analytics(limit)


@app.get("/performance-dashboard", response_class=HTMLResponse)
def performance_dashboard(request: Request):
    if not has_access(request):
        return RedirectResponse(url="/login", status_code=303)

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
            <a href="/logout">Logout</a>
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
def tracking_dashboard(request: Request):
    if not has_access(request):
        return RedirectResponse(url="/login", status_code=303)

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
            <a href="/logout">Logout</a>
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

                if (response.status === 401) {
                    alert("Access code required. Please open /login to use paper tracking.");
                    return;
                }

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
