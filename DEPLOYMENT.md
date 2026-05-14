# Smart Job Platform Deployment (VPS)

## One-command run

From project root:

```bash
docker compose up --build -d
```

App URLs after start:
- Frontend: `http://<VPS-IP>:5173`
- Backend API: `http://<VPS-IP>:8001`

## Prerequisites
- Docker installed
- Docker Compose plugin installed
- Ports `5173` and `8001` open in firewall/security group

## Update flow

```bash
git pull
docker compose up --build -d
```

## Health checks

```bash
curl http://localhost:8001/
curl http://localhost:5173/
```

## Logs

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

## Stop

```bash
docker compose down
```

## Local migration note
For an existing local DB created before Alembic:

```bash
cd backend
alembic stamp head
```

For normal schema updates:

```bash
cd backend
alembic upgrade head
```
