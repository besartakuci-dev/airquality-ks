# AirQuality KS

Real-time air quality monitoring and PM2.5 forecasting for Kosovo. The system ingests sensor measurements and weather data, processes them into aggregates, forecasts PM2.5 with machine learning, and serves the results through an API and a web dashboard.

University course project: Data Processing Systems.

## Architecture

OpenAQ (air quality) and Open-Meteo (weather) data is published to Kafka, validated and aggregated by Spark, stored in PostgreSQL, used to train PM2.5 forecasting models, and served through a cached FastAPI backend to a React dashboard.

- Full architecture, diagrams and component owners: [docs/architecture.md](docs/architecture.md)
- Architecture decisions and alternatives: [docs/adr.md](docs/adr.md)

```
 OpenAQ / Open-Meteo ──► ingestion/ (Python producers)
                        │
                        ▼
                  Apache Kafka  (topics: air-quality-raw, weather-raw)
                        │
                        ▼
               processing/ (PySpark: Structured Streaming + batch)
                        │
                        ▼
        PostgreSQL (storage)  ◄──►  ml/ (scikit-learn / XGBoost)
                        │
                        ▼
          api/ (FastAPI) ◄──► Redis (cache)
                        │
                        ▼
          dashboard/ (React + TypeScript + Vite)
```

| Folder | Purpose |
| --- | --- |
| `ingestion/` | Python producers that publish raw data to Kafka |
| `processing/` | PySpark streaming and batch jobs |
| `ml/` | PM2.5 forecasting models |
| `api/` | FastAPI backend |
| `dashboard/` | React frontend |
| `db/` | Alembic migrations (`db/migrations/`) |
| `deploy/` | Deployment config (Kubernetes, later) |
| `tests/` | Test suites (`tests/api/`, …) |
| `docs/` | Feature docs and changelog |

Local development runs on Docker Compose; CI runs on GitHub Actions.

## Technology versions

Every version below is pinned exactly in the repo.

| Technology | Version | Where it's pinned |
| --- | --- | --- |
| PostgreSQL | 18.6 (`postgres:18.6-alpine`) | `docker-compose.yml` |
| Redis | 8.8.4 (`redis:8.8.4-alpine`) | `docker-compose.yml` |
| Apache Kafka (KRaft) | 4.4.0 (`apache/kafka:4.4.0`) | `docker-compose.yml` |
| Apache Spark / PySpark | 4.2.1 (`apache/spark:4.2.1-python3`) | `docker-compose.yml` |
| Python (API image) | 3.12.16 (`python:3.12.16-slim`) | `api/Dockerfile` |
| FastAPI | 0.162.0 | `api/requirements.txt` |
| Uvicorn | 0.54.0 | `api/requirements.txt` |
| pydantic-settings | 2.16.2 | `api/requirements.txt` |
| SQLAlchemy | 2.1.8 | `api/requirements.txt` |
| psycopg | 3.3.7 | `api/requirements.txt` |
| Alembic | 1.20.1 | `api/requirements.txt` |
| redis-py | 8.1.0 | `api/requirements.txt` |
| pytest | 9.2.0 | `api/requirements-dev.txt` |
| httpx2 | 2.16.0 | `api/requirements-dev.txt` |
| Ruff | 0.17.3 | `api/requirements-dev.txt` |
| Node.js (dashboard image, CI) | 24.22.2 (`node:24.22.2-alpine`) | `dashboard/Dockerfile`, `ci.yml` |
| React | 19.3.1 | `dashboard/package.json` |
| TypeScript | 7.0.2 | `dashboard/package.json` |
| Vite | 8.3.5 | `dashboard/package.json` |
| @vitejs/plugin-react | 6.2.1 | `dashboard/package.json` |
| Oxlint | 1.91.0 | `dashboard/package.json` |
| GitHub Actions: checkout / setup-python / setup-node | 7.0.1 / 7.1.0 / 7.1.0 | `.github/workflows/ci.yml` |

scikit-learn, XGBoost and the PySpark job dependencies will be pinned when the `ml/` and `processing/` code is added.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine with the Compose plugin)
- GNU Make. On Windows, install it with `winget install GnuWin32.Make` or `choco install make`, or run the `docker compose` commands from the `Makefile` directly.
- For running tests and the dashboard outside Docker: Python 3.12+ and Node.js 22.12+

## Setup

```bash
cp .env.example .env     # then replace the placeholder passwords
make up                  # build images and start all services
```

| Command | What it does |
| --- | --- |
| `make up` | Build images and start every service |
| `make down` | Stop and remove containers (volumes are kept) |
| `make logs` | Follow all logs (`make logs s=api` for one service) |
| `make test` | Run the API tests locally (`pip install -r api/requirements-dev.txt` first) |
| `make migrate` | Apply Alembic migrations inside the `api` container |

## Verify it's running

```bash
docker compose ps                     # every service should be "healthy" (kafka-init: "exited (0)")
curl http://localhost:8000/health/ready
# {"status":"ok","checks":{"postgres":"ok","redis":"ok"}}

docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
# air-quality-raw
# weather-raw
```

| Service | URL (default ports) |
| --- | --- |
| API health | http://localhost:8000/health |
| API readiness | http://localhost:8000/health/ready |
| API docs | http://localhost:8000/docs |
| Spark master UI | http://localhost:8080 |
| Spark worker UI | http://localhost:8081 |
| Dashboard | http://localhost:5173 |
| Kafka (from the host) | `localhost:9094` (inside Docker: `kafka:9092`) |

Ports are set in `.env`.

## Team

- TBD
