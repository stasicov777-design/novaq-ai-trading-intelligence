# NOVAQ AI Trading Intelligence

AI Decision Intelligence Layer for crypto markets. Educational analytics only. Not financial advice.

## Features

- Live market data
- Market State Engine
- Candle Data Layer
- Signal Engine
- Opportunity Score
- Decision Feed
- Paper Signal Tracking
- Auto Evaluation
- Performance Analytics
- Web dashboards

## Local Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
```

Install:

```bash
pip install -r requirements.txt
```

Run dev:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

## Production Run

```bash
python start.py
```

## Main Dashboards

- `/dashboard`
- `/feed-dashboard`
- `/tracking-dashboard`
- `/performance-dashboard`
- `/docs`

## Main API Endpoints

- `GET /health`
- `GET /market/{symbol}`
- `GET /market-state/{symbol}`
- `GET /candles/{symbol}`
- `GET /signals/{symbol}`
- `GET /decision/{symbol}`
- `GET /feed`
- `GET /tracked-signals`
- `GET /tracking-summary`
- `GET /performance-analytics`

## Deployment Notes

SQLite is OK for a local MVP. For production with many users, move to PostgreSQL.

On Render or Railway, use a persistent disk or volume if SQLite tracking history must be preserved.

- Start command: `python start.py`
- Healthcheck: `/health`

## Disclaimer

Educational analytics only. Not financial advice. NOVAQ AI does not execute trades and does not access user funds.
