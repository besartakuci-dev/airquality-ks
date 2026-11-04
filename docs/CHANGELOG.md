# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Dashboard: pinned dependency versions, `.env.example`, dev Dockerfile.
- API: FastAPI shell with env-based config, SQLAlchemy/psycopg session, Redis client, JSON error handlers, CORS, `GET /health` and `GET /health/ready`.
- Alembic initialized in `db/migrations/` (no migrations yet).
- Docker Compose dev stack: PostgreSQL, Redis, Kafka (KRaft) with topic init, Spark master/worker, API, dashboard.
- Makefile (`up`, `down`, `logs`, `test`, `migrate`) and GitHub Actions CI.
