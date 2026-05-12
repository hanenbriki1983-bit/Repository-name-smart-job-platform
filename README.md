# Smart Job Platform

## Backend Run

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

## Core API Endpoints

- `GET /` Home
- `POST /auth/register` Register
- `POST /auth/login` Login
- `GET /dashboard` Dashboard summary (auth)
- `GET /companies` List companies
- `POST /companies` Create company
- `GET /jobs` List/search jobs (`?q=`)
- `POST /jobs` Create job
- `POST /applications` Apply with CV upload (auth, multipart)
- `GET /applications` My applications (auth)
- `POST /ai/suggest-jobs` AI-like job matching by skills

## SQL Database

Uses SQLite file: `backend/jobs.db` with tables:
- `users`
- `companies`
- `jobs`
- `applications`

## Frontend Pages To Build

- Home
- Login
- Register
- Jobs
- Dashboard
