# Architecture Decision Records

This file records the main architecture decisions for AirQuality KS. Each record states the context, the decision, the alternatives we rejected and the trade-offs we accept. Versions match the pinned versions in the [README](../README.md#technology-versions).

See [architecture.md](architecture.md) for how the components fit together.

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-001](#adr-001-apache-kafka-for-ingestion-instead-of-direct-api-polling) | Apache Kafka for ingestion | Accepted |
| [ADR-002](#adr-002-apache-spark-for-stream-and-batch-processing-instead-of-pandas) | Apache Spark for processing | Accepted |
| [ADR-003](#adr-003-postgresql-instead-of-mongodb) | PostgreSQL for storage | Accepted |
| [ADR-004](#adr-004-redis-as-a-cache-for-expensive-read-endpoints) | Redis as a read cache | Accepted |
| [ADR-005](#adr-005-fastapi-instead-of-nodejs-for-the-backend) | FastAPI for the backend | Accepted |
| [ADR-006](#adr-006-xgboost-for-pm25-forecasting-instead-of-linear-regression-or-lstm) | XGBoost for forecasting | Accepted |
| [ADR-007](#adr-007-docker-compose-for-development-local-kubernetes-for-a-production-like-environment-github-actions-for-ci) | Docker Compose + local Kubernetes + GitHub Actions | Accepted |

---

## ADR-001: Apache Kafka for ingestion instead of direct API polling

### Status

Accepted

### Context

We collect air quality measurements from OpenAQ and weather data from Open-Meteo. The data has to be validated, aggregated, stored and used for ML training. External APIs can be slow or unavailable, and our processing jobs can be down for restarts or deployments.

### Decision

Ingestion producers publish raw records to Apache Kafka 4.4.0 (KRaft mode, no ZooKeeper). There is one topic per source: `air-quality-raw` and `weather-raw`. Spark consumes from Kafka. Producers never write to the database directly.

### Alternatives considered

- A script that polls the APIs and inserts rows directly into PostgreSQL.
- A lightweight queue such as Redis Streams or RabbitMQ.

### Reasons for rejection

- Direct polling couples fetching to processing: if validation or the database fails, the data is lost or the poller has to retry on its own. It also cannot replay old data after a bug fix.
- RabbitMQ deletes messages once they are consumed, so replaying them is hard. Redis Streams keeps data in memory, which limits how much history we can retain. Spark has no built-in source for either.

### Consequences

- Producers and processing are decoupled. Kafka buffers data while consumers are down.
- Retained topics can be replayed to reprocess data, and several consumers (streaming validation, batch jobs) can read the same topic independently.
- Trade-off: Kafka is another service to run and monitor. Locally it is a single broker with replication factor 1, so it is not fault-tolerant.
- Producers must use a stable message schema, because changing it affects every consumer.

---

## ADR-002: Apache Spark for stream and batch processing instead of Pandas

### Status

Accepted

### Context

We process measurements from several Kosovo cities together with hourly weather data. This covers the live stream as well as multi-year history used for training. Streaming data arrives late and out of order and has to be validated and aggregated in time windows.

### Decision

We use Apache Spark / PySpark 4.2.1 for both modes:

- **Structured Streaming** reads from Kafka, validates records, writes valid rows to `measurements` and invalid rows to `rejected_records`, and computes windowed aggregates with watermarks for late data.
- **Batch jobs** do feature engineering and prepare training data from the history in PostgreSQL.

### Alternatives considered

- Pandas scripts on a schedule (cron).
- Pandas for batch work plus a separate stream processor (for example Kafka Streams or Faust).

### Reasons for rejection

- Pandas runs on a single machine and needs the whole dataset in memory. It has no native streaming support, watermarks or checkpointed Kafka offsets for recovery.
- Two separate tools would mean two codebases for the same validation and aggregation logic.

### Consequences

- The same DataFrame API is used for streaming and batch, and the work can scale horizontally by adding Spark workers.
- Trade-off: Spark adds JVM overhead, slower start-up and harder local debugging. For small data it can be slower than Pandas.
- The volume argument is an assumption for now. It will be validated by a **Spark vs. Pandas benchmark** later in the project, and this ADR will be updated with the measured results.

---

## ADR-003: PostgreSQL instead of MongoDB

### Status

Accepted

### Context

Our data is structured and relational: stations belong to cities; measurements, weather and aggregates belong to stations and time ranges; predictions belong to model runs; users have roles. Most queries filter by station and time range. Data quality is a course requirement.

### Decision

We use PostgreSQL 18.6 as the main data store, with SQLAlchemy 2.1.8 and psycopg 3.3.7 as the access layer and Alembic 1.20.1 for schema migrations. The schema is normalized to 3NF and uses primary keys, foreign keys, `CHECK` constraints (for example, non-negative pollutant values) and indexes on `(station_id, timestamp)` columns. The final schema is defined in the ERD ([erd.md](erd.md)).

### Alternatives considered

- MongoDB (document store).
- A dedicated time-series database such as InfluxDB.

### Reasons for rejection

- MongoDB does not enforce relationships or a schema the way foreign keys and `CHECK` constraints do. Integrity would move into application code, and joins between entities would be harder.
- InfluxDB is a good fit for metrics but a poor fit for relational entities such as users, roles, stations and model runs. We would still need a second database for those.

### Consequences

- The database enforces data integrity, and time-range queries are fast thanks to composite indexes.
- Joins and SQL are available for the API, the analytics and the ML batch jobs.
- Trade-off: schema changes need migrations. Very large time-series tables may later need partitioning (for example by month).

---

## ADR-004: Redis as a cache for expensive read endpoints

### Status

Accepted

### Context

The dashboard repeatedly requests the same aggregates (hourly/daily averages per station) and the latest predictions. These queries scan and group many rows, but their results change only when a new aggregation window or model run completes.

### Decision

The API uses Redis 8.8.4 (redis-py 8.1.0) as a read-through cache for expensive read endpoints such as aggregates and predictions. The cache key is built from the endpoint and its query parameters (for example `aggregates:{station}:{interval}:{from}:{to}`). Entries expire after a TTL that matches how often the data refreshes. On a cache miss, the API queries PostgreSQL, stores the result and returns it.

### Alternatives considered

- No cache: every request goes to PostgreSQL.
- An in-process cache in the API (for example `functools.lru_cache`).
- PostgreSQL materialized views only.

### Reasons for rejection

- Without a cache, the same heavy queries run on every dashboard refresh.
- An in-process cache is not shared between API instances or replicas and is lost on restart.
- Materialized views still need a database round trip and a refresh strategy. They complement the cache rather than replace it.

### Consequences

- Repeated reads are faster and the load on PostgreSQL drops.
- Trade-off: data may be stale for up to one TTL. TTL-based invalidation is simple but not instant. Explicit invalidation after aggregation or model runs can be added later.
- If Redis is unavailable, the API should fall back to PostgreSQL instead of failing.

---

## ADR-005: FastAPI instead of Node.js for the backend

### Status

Accepted

### Context

The backend serves measurements, aggregates, predictions and alerts to the dashboard and handles authentication and roles (Admin, Analyst, Public). Ingestion, Spark jobs (PySpark) and ML (scikit-learn, XGBoost) are all written in Python.

### Decision

We build the API with FastAPI 0.162.0 on Uvicorn 0.54.0 (Python 3.12.16), using Pydantic / pydantic-settings 2.16.2 for configuration and request/response validation. Authentication uses JWT with role-based access control.

### Alternatives considered

- Node.js with Express or NestJS.
- Django REST Framework.

### Reasons for rejection

- Node.js would add a second backend language. Trained models could not be loaded directly and would need a separate Python model service or a model export format, and shared validation logic would be duplicated.
- Django is heavier than we need (ORM, admin and templates), and its async support and automatic OpenAPI docs are less direct than in FastAPI.

### Consequences

- The whole backend uses one language, so the team can share code (schemas, feature functions) between the ingestion, processing, ML and API layers.
- Models are loaded directly in the API process for inference.
- Pydantic validates input and output, and OpenAPI docs are generated automatically at `/docs`.
- Trade-off: CPU-heavy inference inside the API can block workers. Heavy work belongs in batch jobs, and the API should mostly serve precomputed predictions.

---

## ADR-006: XGBoost for PM2.5 forecasting instead of linear regression or LSTM

### Status

Accepted

### Context

We forecast PM2.5 per station for the next hours. The features are tabular: lagged PM2.5 values, rolling averages, weather (temperature, humidity, wind, pressure) and calendar features (hour, weekday, season). The dataset is small to medium (a few cities and a few years of hourly data). Relationships such as temperature inversions and low wind in winter are non-linear.

### Decision

We use XGBoost (gradient-boosted trees) as the main model, with features produced by the Spark batch jobs. We keep linear regression as a **baseline**. The final choice will be confirmed by comparing **MAE and RMSE** of XGBoost against the baseline on a time-based hold-out set, and each run is recorded in `model_runs`.

### Alternatives considered

- Linear regression (scikit-learn).
- LSTM / other deep sequence models.

### Reasons for rejection

- Linear regression cannot capture non-linear interactions between weather and pollution without manual feature crosses. It is kept for comparison, not as the main model.
- LSTM needs much more data, longer training, GPU-friendly infrastructure and careful tuning. It is also harder to interpret, which is too costly for our data size and timeline.

### Consequences

- XGBoost handles non-linear relationships and missing values and trains quickly on CPU.
- Feature importance explains which inputs drive the forecast, which is useful for the report and for analysts.
- Trade-off: forecast quality depends on good lag and weather features. XGBoost does not model long sequences directly.
- The scikit-learn and XGBoost versions will be pinned when `ml/` code is added.

---

## ADR-007: Docker Compose for development, local Kubernetes for a production-like environment, GitHub Actions for CI

### Status

Accepted

### Context

The system has many services (PostgreSQL, Redis, Kafka, Spark master/worker, API, dashboard, and later producers and jobs). Three developers on different machines need the same environment. The course asks for a production-like deployment, but the system is **not publicly hosted**.

### Decision

- **Development:** Docker Compose (`docker-compose.yml`, `make up`) runs the full stack with pinned images and `.env`-based configuration and health checks.
- **Production-like environment:** local Kubernetes using **minikube or kind**, with manifests in `deploy/`. This shows deployments, services, config/secrets and scaling without a cloud provider.
- **CI:** GitHub Actions (`.github/workflows/ci.yml`) runs on every pull request to `dev` and `main`. It lints and tests the API (Ruff 0.17.3, pytest 9.2.0), lints and builds the dashboard (Node.js 24.22.2, Oxlint 1.91.0), validates the Compose file and builds the Docker images.

### Alternatives considered

- Installing every service manually on each machine.
- A managed cloud deployment (for example a managed Kubernetes service or a PaaS).

### Reasons for rejection

- Manual installation leads to version drift between machines.
- Cloud hosting adds cost, account management and public security concerns that the course does not need.

### Consequences

- One command starts a reproducible stack, and CI catches broken builds before merge.
- Trade-off: the full stack needs a lot of local RAM and CPU (Kafka + Spark).
- Two deployment definitions (Compose and Kubernetes) must be kept in sync.
- Local Kubernetes is not a real production environment: there is no high availability, no public ingress and no managed backups.
