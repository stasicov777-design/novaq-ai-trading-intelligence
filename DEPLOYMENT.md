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

## Docker

```bash
docker build -t novaq-ai .
docker run -p 8000:8000 novaq-ai
```
