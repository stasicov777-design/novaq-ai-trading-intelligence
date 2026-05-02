# Deployment Guide

## Railway

1. Push project to GitHub.
2. Create a Railway project from the GitHub repo.
3. Start command: `python start.py`.
4. Set `PORT` automatically or leave default.
5. Open `/health` and `/docs`.

## Render

1. Create a New Web Service.
2. Build command: `pip install -r requirements.txt`.
3. Start command: `python start.py`.
4. Healthcheck path: `/health`.
5. Add a persistent disk if SQLite tracking history must persist.

### Render Environment Variables

```text
ACCESS_CONTROL_ENABLED=true
ACCESS_CODE=<your-secret-access-code>
```

Without `ACCESS_CODE`, the app uses the default demo code. For public deployment, always set a custom `ACCESS_CODE` in Render.

## PostgreSQL on Render

1. Create a managed PostgreSQL database.
2. Copy the Internal Database URL or External Database URL.
3. Add it to the web service Environment Variables as:
   `DATABASE_URL=<your-postgres-url>`
4. Redeploy the service.
5. The app will auto-create required tables:
   `tracked_signals`
   `feedback_entries`

Note:
Without `DATABASE_URL`, the app uses SQLite fallback. SQLite is acceptable for demo, but PostgreSQL is recommended for real beta users.

## Docker

```bash
docker build -t novaq-ai .
docker run -p 8000:8000 novaq-ai
```
