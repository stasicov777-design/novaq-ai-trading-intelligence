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

- `/` public landing page
- `/dashboard`
- `/feed-dashboard`
- `/tracking-dashboard`
- `/performance-dashboard`
- `/docs`

## Main API Endpoints

- `GET /api` - service metadata JSON
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

## Demo Access Control

- Tracking and performance dashboards are protected by an access code.
- Set `ACCESS_CODE` in production environment variables.
- Public pages remain available:
  - `/`
  - `/feed-dashboard`
  - `/dashboard`
  - `/docs`
- Protected pages:
  - `/tracking-dashboard`
  - `/performance-dashboard`
  - tracking/evaluation endpoints

## Beta Feedback

- Public feedback page: `/feedback`
- Protected admin feedback dashboard: `/admin-feedback`
- Protected feedback API:
  - `/api/feedback-summary`
  - `/api/feedback`

## Beta Guide

Public beta onboarding page:

- `/beta`

It explains how to test the product, how to read decisions, and how to send useful feedback.

## Trade Levels / Invalidation

NOVAQ AI provides educational trade context:

- invalidation level
- stop zone
- take profit zone
- risk/reward ratio
- decision validity window

These values are generated from recent candle structure and are not financial advice.

## Language Switch

Public pages support EN / UA language switching without browser auto-translation.
Technical enum values remain in English to avoid incorrect translations.

## Storage

NOVAQ AI supports two storage modes:

- SQLite fallback for local MVP development
- PostgreSQL for production when `DATABASE_URL` is set

Tracking and feedback data use PostgreSQL automatically if `DATABASE_URL` starts with `postgres://` or `postgresql://`.

## Health Checks

- `/health` - lightweight app health
- `/health/db` - storage backend and table connectivity check

The DB health endpoint does not expose `DATABASE_URL` or credentials.

## Deployment Notes

SQLite is OK for a local MVP. For production with many users, move to PostgreSQL.

On Render or Railway, use a persistent disk or volume if SQLite tracking history must be preserved.

- Start command: `python start.py`
- Healthcheck: `/health`

## Disclaimer

Educational analytics only. Not financial advice. NOVAQ AI does not execute trades and does not access user funds.
