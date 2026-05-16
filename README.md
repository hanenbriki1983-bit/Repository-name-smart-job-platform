# Smart Job Platform

Production-ready full-stack app with:
- FastAPI backend
- React/Vite frontend
- PostgreSQL database
- Alembic migrations
- PWA install support

## Local Development

### 1) Backend

```powershell
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8001
```

### 2) Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open: `http://localhost:5173`

## Environment Variables

### Backend (`backend/.env`)

- `DATABASE_URL` (required in production)
- `CORS_ORIGINS` (comma-separated)
- `JOB_API_PROVIDER` (`adzuna` or `jsearch`)
- `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` (for Adzuna provider)
- `RAPIDAPI_KEY` (for JSearch provider)

Example in [backend/.env.example](C:/Users/ASUS/smart-job-platform/backend/.env.example)

### Frontend (`frontend/.env`)

- `VITE_API_URL` (backend base URL)

Example in [frontend/.env.example](C:/Users/ASUS/smart-job-platform/frontend/.env.example)

## Database Migrations

```powershell
cd backend
alembic upgrade head
```

Create a new migration:

```powershell
cd backend
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

## Docker Compose (PostgreSQL)

```bash
docker compose up --build -d
```

Services:
- Postgres: `localhost:5432`
- Backend: `localhost:8001`
- Frontend: `localhost:5173`

## Deploy

- Render backend config: [render.yaml](C:/Users/ASUS/smart-job-platform/render.yaml)
- Railway backend config: [railway.toml](C:/Users/ASUS/smart-job-platform/railway.toml)
- Vercel frontend config: [vercel.json](C:/Users/ASUS/smart-job-platform/vercel.json)
- Process fallback: [Procfile](C:/Users/ASUS/smart-job-platform/Procfile)

## PWA

PWA is enabled via `vite-plugin-pwa` with auto-update service worker and installable manifest.
