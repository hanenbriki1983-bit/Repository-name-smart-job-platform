# Deployment Guide

## Backend on Render

1. Push repo to GitHub.
2. In Render, create PostgreSQL service.
3. Create Web Service from repo using [render.yaml](C:/Users/ASUS/smart-job-platform/render.yaml).
4. Set `CORS_ORIGINS` to your Vercel domain.
5. Render runs:

```bash
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Backend on Railway

1. Create new Railway project from repo.
2. Add PostgreSQL plugin.
3. Set env vars:
   - `DATABASE_URL` (Railway Postgres connection)
   - `CORS_ORIGINS` (your Vercel URL)
4. Railway uses [railway.toml](C:/Users/ASUS/smart-job-platform/railway.toml).

## Frontend on Vercel

1. Import the same repo into Vercel.
2. Use [vercel.json](C:/Users/ASUS/smart-job-platform/vercel.json).
3. Set env var:
   - `VITE_API_URL=https://your-backend-domain`
4. Deploy.

## PWA Installability

PWA config is in [vite.config.js](C:/Users/ASUS/smart-job-platform/frontend/vite.config.js) using `vite-plugin-pwa`.

Install prompts will appear on supported browsers after deployment over HTTPS.

## Local Production-like Stack

```bash
docker compose up --build -d
```

## Health Checks

- Backend: `GET /` at `https://your-backend-domain/`
- Frontend: open your Vercel URL
- Swagger: `https://your-backend-domain/docs`
