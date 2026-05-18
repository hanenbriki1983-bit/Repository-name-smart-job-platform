# Deployment Guide

## Full Stack on Render (Recommended)

1. Push repo to GitHub.
2. In Render, create a new Blueprint and select the repo.
3. Render will provision all services from [render.yaml](C:/Users/ASUS/smart-job-platform/render.yaml):
   - `smart-job-frontend` (Static Site)
   - `smart-job-backend` (Web Service)
   - `smart-job-db` (PostgreSQL)
4. In Render dashboard, update backend env var `CORS_ORIGINS` to your actual frontend URL:
   - `https://smart-job-frontend.onrender.com` (or your custom domain)
5. Set frontend env var `VITE_API_URL` to your backend URL:
   - `https://smart-job-backend.onrender.com`
6. Backend start command:

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

## Frontend on Render (Manual Static Site Option)

If you do not use Blueprint:
1. Create a **Static Site** in Render.
2. Configure:
   - Root Directory: `frontend`
   - Build Command: `npm ci && npm run build`
   - Publish Directory: `dist`
3. Add rewrite rule for SPA:
   - Source: `/*`
   - Destination: `/index.html`
4. Set env var:
   - `VITE_API_URL=https://your-backend-domain`

## PWA Installability

PWA config is in [vite.config.js](C:/Users/ASUS/smart-job-platform/frontend/vite.config.js) using `vite-plugin-pwa`.

Install prompts will appear on supported browsers after deployment over HTTPS.

## Local Production-like Stack

```bash
docker compose up --build -d
```

## Health Checks

- Backend: `GET /` at `https://your-backend-domain/`
- Frontend: open your Render frontend URL
- Swagger: `https://your-backend-domain/docs`
