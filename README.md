# documind
RAG-based document Q&amp;A app built with FastAPI, PostgreSQL/pgvector, and LangChain. Upload documents and query them with natural language.

## Local backend with Docker

The backend runs as three long-running services using one image: the FastAPI API, a Celery worker, and the processing dispatcher. A separate migration service applies Alembic migrations before those services start.

This Compose setup is for local development. It uses LocalStack and exposes the API only on the host's loopback interface. Production hosting and HTTPS are separate deployment work.

### Configuration

Use Docker Engine with the Compose and Buildx plugins. Create the root `.env` and `backend/.env` from their respective `.env.example` files if they do not already exist. Keep existing configuration when upgrading an existing checkout.

The root `.env` supplies `POSTGRES_PASSWORD`, `LOCALSTACK_AUTH_TOKEN`, `DOCUMIND_S3_BUCKET`, and `DOCUMIND_S3_REGION`. The database password must match the existing PostgreSQL volume. The local Compose database URL interpolates this password directly, so use URL-unreserved characters: letters, digits, hyphens, periods, underscores, and tildes.

The backend reads its remaining settings from `backend/.env`, including `DOCUMIND_OPENAI_API_KEY`, `DOCUMIND_ANSWER_MODEL`, and the local S3 credentials. Compose overrides database, Redis, and S3 addresses with Docker service names. Environment files are supplied at runtime and are excluded from the image.

Optional root `.env` settings:

| Setting | Default | Purpose |
| --- | --- | --- |
| `DOCUMIND_WORKER_CONCURRENCY` | `2` | Number of Celery worker processes. |
| `DOCUMIND_WORKER_STOP_GRACE_PERIOD` | `5m` | Time allowed for worker shutdown before Docker force-stops it. |

### Start and verify

Stop API, Celery worker, and dispatcher processes started manually before switching to Compose. This frees port 8000 and ensures jobs are handled by the containerized worker.

Run from the repository root:

```bash
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 180
docker compose ps --all
docker compose logs --tail=100 migrate api worker dispatcher
```

The `migrate` container should finish with exit code 0. The API should become healthy, and the worker and dispatcher should remain running. The API health check uses `/ready` to check database connectivity. A running worker or dispatcher still requires a functional check: upload a text-based PDF through the frontend, wait for Ready to ask, then ask a question and check its sources.

Start the frontend separately using [its instructions](frontend/README.md). Its backend URL remains `http://127.0.0.1:8000`.

### Updates and shutdown

After backend code or dependency changes, rebuild and recreate the backend services. Stop them first so migrations run without the previous application version processing requests:

```bash
docker compose stop api worker dispatcher
docker compose up -d --build --wait --wait-timeout 180
```

To stop the full stack while retaining its data:

```bash
docker compose stop
```

Named volumes retain PostgreSQL, Redis, and LocalStack data. Do not use `docker compose down --volumes` unless you intend to delete that data.

Long-running services use `restart: unless-stopped`. Docker must itself start on boot; explicitly stopped containers stay stopped. Compose dependency checks apply during Compose startup, not Docker daemon restart, and restart policies do not restart a container merely because its health check fails.
