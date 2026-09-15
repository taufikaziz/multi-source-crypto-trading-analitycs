# Multi-Source Crypto Trading Analytics Platform

A production-grade analytical data platform for analyzing cryptocurrency market data, trading activity, and user behavior from multiple sources.

## Problem Statement

Cryptocurrency exchanges generate vast amounts of data across multiple systems:
- Public market data (Indodax API)
- Internal transactional data (PostgreSQL orders, trades, users)
- User behavior analytics (MongoDB event logs)

This platform integrates all data sources to provide comprehensive analytics on:
- Crypto price performance
- Market volume & trading activity
- User engagement patterns
- Business metrics across all dimensions

## Business Questions

1. **How is crypto price performance changing daily?**
2. **Which cryptocurrencies have the highest market volume?**
3. **How does trading activity evolve over time?**
4. **Is there a correlation between price and volume?**
5. **How does user activity change daily?**
6. **How do market, trading, and user activities interconnect?**

## Architecture

```
+------------------+      +------------------+      +------------------+
¦   Indodax API    ¦      ¦   PostgreSQL     ¦      ¦   MongoDB        ¦
¦   Market Data    ¦      ¦  (orders/trades) ¦      ¦ (user_events)    ¦
+------------------+      +------------------+      +------------------+
         ¦ async HTTP              ¦ async pg         ¦ async mongo
         ?                         ?                  ?
    +----------------------------------------------------+
    ¦           Async Ingestion Layer                    ¦
    ¦   (aiohttp/asyncpg/motor + watermark)              ¦
    +----------------------------------------------------+
                              ¦
                              ?
                    +------------------+
                    ¦     MinIO        ¦
                    ¦  (Bronze Storage)¦
                    +------------------+
                             ¦
                             ¦ dbt
                             ?
                    +------------------+
                    ¦       dbt        ¦
                    ¦  (Staging ?      ¦
                    ¦   Intermediate ? ¦
                    ¦    Marts)        ¦
                    +------------------+
                             ¦
                             ?
                    +------------------+
                    ¦    Databricks    ¦
                    ¦  SQL Warehouse   ¦
                    +------------------+
                             ?
                             ¦
                    +------------------+
                    ¦   Airflow 3      ¦
                    ¦  (1 DAG via     ¦
                    ¦   5 tasks)       ¦
                    +------------------+
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Ingestion | Python, aiohttp, asyncpg, Motor | Async data extraction |
| Bronze | MinIO, Parquet, JSON | Raw data object storage |
| Transformation | dbt (DuckDB + Databricks) | ELT transformation layer |
| Orchestration | Airflow 3 | Workflow scheduling |
| Warehouse | Databricks SQL Warehouse | Analytical data warehouse |

## Data Sources

### 1. Indodax API (Public)
- `/api/pairs` - Trading pairs metadata
- `/api/summaries` - Real-time market summaries

### 2. PostgreSQL (Operational)
- `users` - User accounts
- `orders` - Trading orders
- `trades` - Executed trades
- `transactions` - Asset movements

### 3. MongoDB (Analytics)
- `user_events` - User behavior tracking

## Getting Started

### Prerequisites
- Python 3.9+
- Docker & Docker Compose
- 8GB RAM (development environment)

### Local Development

1. **Clone and setup environment:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

2. **Start infrastructure:**
```bash
cd airflow-docker
docker compose up -d
```

3. **Access services:**
- Airflow UI: http://localhost:8080
- MinIO Console: http://localhost:9001
- MongoDB: localhost:27017

4. **Run dbt models:**
```bash
dbt build --target dev
```

## Project Structure

```
src/
+-- ingestion/      # Async extraction clients
+-- storage/        # MinIO abstraction
+-- bronze/         # Bronze layer writing
+-- silver/         # Silver layer (legacy)
+-- gold/           # Gold layer (legacy)
+-- quality/        # Data quality checks
+-- warehouse/      # Databricks loader

airflow-docker/     # Airflow + services
dbt_crypto_platform/ # dbt project
dags/               # Airflow DAGs
docs/               # Documentation
tests/              # Test suite
```

## Data Flow

1. **Ingestion** (tasks extract_indodax, extract_postgresql, extract_mongodb - paralel)
   - Async extraction from all sources
   - Write to MinIO Bronze layer
   - Update watermarks only after success

2. **Transformation** (task dbt_build_warehouse)
   - dbt staging (cleaning, normalization)
   - dbt intermediate (joins, enrichment)
   - dbt marts (Gold business metrics)

3. **Warehouse Load** (task load_bronze_to_databricks)
   - Load Bronze objects from MinIO to Databricks staging

## Data Quality

All data quality checks are implemented as dbt tests:
- `not_null`, `unique` constraints
- Business rules (e.g., `filled_quantity <= quantity`)
- Cross-source validation

## Testing

Run test suite:
```bash
pytest tests/
```

Test coverage:
- Ingestion framework, retry dan source ingestion
- dbt models, transformer dan quality check
- Airflow DAG, idempotency dan failure scenarios (total 57 tests, 16 file)

## Production Deployment

1. **Databricks Setup**
   - Create SQL Warehouse
   - Configure credentials via environment variables

2. **MinIO Setup**
   - Configure production bucket
   - Set up backup strategy

3. **Airflow**
   - Use ExternalExecutor for production
   - Configure monitoring & alerting

## Environment Variables

See `.env.example` for complete list. Key variables:

| Variable | Purpose |
|----------|---------|
| `POSTGRES_*` | PostgreSQL connection |
| `MONGO_*` | MongoDB connection |
| `MINIO_*` | MinIO configuration |
| `DATABRICKS_*` | Databricks connection |
| `AIRFLOW_*` | Airflow configuration |

## License

MIT License
