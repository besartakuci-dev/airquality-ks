# Architecture

AirQuality KS collects air quality and weather data for Kosovo, validates and aggregates it, forecasts PM2.5 and shows the results on a web dashboard. The reasoning behind each technology choice is in [adr.md](adr.md).

## Layers

| Layer | What it does | Technology |
| --- | --- | --- |
| Ingestion | Python producers fetch data from OpenAQ (air quality) and Open-Meteo (weather) and publish raw JSON records. | Python producers (`ingestion/`) |
| Messaging | Buffers raw records and decouples producers from processing. Topics: `air-quality-raw`, `weather-raw`. | Apache Kafka 4.4.0 (KRaft) |
| Processing | Structured Streaming validates records and computes windowed aggregates. Batch jobs do feature engineering and prepare training data. | Apache Spark / PySpark 4.2.1 (`processing/`) |
| Storage | Stores stations, measurements, weather, aggregates, alerts, predictions, model runs, rejected records, users and roles. | PostgreSQL 18.6, Alembic 1.20.1 (`db/`) |
| ML | Trains and evaluates PM2.5 forecasting models and writes predictions. | XGBoost, linear regression baseline (`ml/`) |
| API | REST endpoints with JWT auth and roles. Caches expensive reads. | FastAPI 0.162.0, Redis 8.8.4 (`api/`) |
| Presentation | Maps, charts, filters and alerts for users. | React 19.3.1, TypeScript 7.0.2, Vite 8.3.5 (`dashboard/`) |

## Component diagram

```mermaid
flowchart LR
    subgraph sources["External sources"]
        openaq["OpenAQ API"]
        openmeteo["Open-Meteo API"]
    end

    subgraph ingestion["Ingestion"]
        aqprod["Air quality producer"]
        wxprod["Weather producer"]
    end

    subgraph messaging["Messaging: Apache Kafka"]
        aqtopic[["air-quality-raw"]]
        wxtopic[["weather-raw"]]
    end

    subgraph processing["Processing: Apache Spark"]
        stream["Structured Streaming<br/>validation + aggregation"]
        batch["Batch jobs<br/>feature engineering + training"]
    end

    subgraph storage["Storage: PostgreSQL"]
        db[("stations, measurements, weather,<br/>aggregates, alerts, predictions,<br/>model_runs, users, roles")]
        rejected[("rejected_records")]
    end

    subgraph serving["API"]
        api["FastAPI<br/>JWT auth + roles"]
        cache[("Redis cache")]
    end

    dashboard["React dashboard"]

    openaq --> aqprod
    openmeteo --> wxprod
    aqprod --> aqtopic
    wxprod --> wxtopic
    aqtopic --> stream
    wxtopic --> stream
    stream -->|valid| db
    stream -->|invalid + reason| rejected
    db --> batch
    batch -->|features, predictions, model_runs| db
    db --> api
    api <-->|TTL cache| cache
    api -->|JSON over HTTP| dashboard
```

## Data flow for one measurement

```mermaid
sequenceDiagram
    autonumber
    participant OA as OpenAQ API
    participant P as Air quality producer
    participant K as Kafka (air-quality-raw)
    participant S as Spark Structured Streaming
    participant DB as PostgreSQL
    participant API as FastAPI
    participant R as Redis
    participant D as React dashboard

    P->>OA: Fetch latest measurements
    OA-->>P: JSON response
    P->>K: Publish raw record
    K-->>S: Consume record (micro-batch)
    S->>S: Validate (range, required fields, duplicates, late data)
    alt Record is valid
        S->>DB: INSERT into measurements
    else Record is invalid
        S->>DB: INSERT into rejected_records (with reason)
    end
    S->>DB: Update aggregates (windowed, watermark)

    D->>API: GET aggregates (JWT)
    API->>R: Check cache
    alt Cache hit
        R-->>API: Cached result
    else Cache miss
        API->>DB: Query aggregates
        DB-->>API: Rows
        API->>R: Store result with TTL
    end
    API-->>D: JSON response
    D->>D: Render chart
```

## Components and owners

| Component | Responsibility | Technology | Owner |
| --- | --- | --- | --- |
| Measurements | OpenAQ producer, `air-quality-raw` topic, streaming validation, `measurements` and `rejected_records` tables | Python, Kafka, PySpark, PostgreSQL | Shqiprimi |
| Weather and aggregates | Open-Meteo producer, `weather-raw` topic, `weather` table, windowed aggregates | Python, Kafka, PySpark, PostgreSQL | Rona |
| ML forecasting | EDA, feature engineering (Spark batch), model training and evaluation, `predictions` and `model_runs` | PySpark, XGBoost, scikit-learn | Besarta |
| Infrastructure | Docker Compose, local Kubernetes, CI, migrations, API shell, Redis cache | Docker, minikube/kind, GitHub Actions, Alembic, FastAPI | Besarta + Shqiprimi |

## Data model (overview)

The planned tables are listed below. The final schema, including columns, keys and constraints, is defined in the ERD by Shqiprimi ([erd.md](erd.md)).

| Table | Contents |
| --- | --- |
| `stations` | Monitoring stations and their location (city, coordinates) |
| `measurements` | Validated pollutant readings per station and timestamp |
| `weather` | Hourly weather observations per location |
| `aggregates` | Hourly/daily statistics per station and pollutant |
| `alerts` | Threshold breaches (for example, PM2.5 above a limit) |
| `predictions` | Forecast PM2.5 values per station and target time |
| `model_runs` | Training runs: model type, parameters, metrics (MAE, RMSE) |
| `rejected_records` | Raw records that failed validation, with the rejection reason |
| `users` | Dashboard and API users |
| `roles` | Admin, Analyst, Public |

## Environments

- **Development:** Docker Compose (`make up`). See the [README](../README.md#setup).
- **Production-like:** local Kubernetes (minikube or kind) with manifests in `deploy/`. The system is not publicly hosted.
- **CI:** GitHub Actions runs on pull requests to `dev` and `main`.
