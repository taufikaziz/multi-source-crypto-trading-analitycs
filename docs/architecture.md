# Architecture Documentation

## Overview

This document describes the complete architecture of the Multi-Source Crypto Trading Analytics Platform.

## Design Decisions

### Why Medallion Architecture?

**Bronze → Silver → Gold** pattern provides:
- **Bronze**: Immutable raw data, replayable
- **Silver**: Cleaned, validated staging layer
- **Gold**: Business-ready analytical marts

### Why dbt Instead of Pandas?

**Transformation Logic:**
- SQL is better for aggregations and joins
- dbt provides testing, documentation, lineage
- Same code works for local (DuckDB) and production (Databricks)
- Declarative approach easier to maintain

**When to Keep Python:**
- Complex API parsing
- Pre-validation before storage
- Non-SQL transformations

### Why Watermark in PostgreSQL?

**Single Source of Truth:**
- Centralized watermark management
- Safe updates (only after Bronze write success)
- Audit trail via updated_at
- No dependency on Airflow state

### Why Airflow 3?

**Modern Orchestration:**
- Dataset-based dependencies (not cron)
- Better task retry logic
- Improved observability
- LocalExecutor sufficient for 8GB RAM

## Data Contracts

### Bronze Layer

**Indodax (JSON):**
- pairs, summaries

**PostgreSQL (Parquet):**
- users, accounts, assets, orders, trades, transactions

**MongoDB (JSON):**
- user_events

### Silver Layer (dbt Staging)

**9 Models:**
- stg_indodax__pairs, stg_indodax__summaries
- stg_postgres__users through stg_postgres__transactions
- stg_mongodb__user_events

### Gold Layer (dbt Marts)

**4 Models:**
- gold_market_daily: Price performance
- gold_trading_daily: Trading activity
- gold_user_activity_daily: User engagement
- gold_crypto_business_metrics: Unified metrics

## Ingestion Strategy

### Incremental Extraction

**Watermark-based:**
- PostgreSQL: updated_at / executed_at
- MongoDB: ingested_at
- Indodax: No watermark (use Bronze captured_at)

**Safe Watermark Updates:**
1. Extract data
2. Validate data
3. Write to Bronze
4. Verify Bronze write
5. Update watermark

### Concurrency

**Async I/O:**
- asyncio.gather() for concurrent extraction
- aiohttp for HTTP requests
- asyncpg for PostgreSQL
- Motor for MongoDB

## Storage Strategy

### MinIO as Bronze

**Benefits:**
- S3-compatible (future-proof)
- Immutable objects
- Versioning support
- Cost-effective

**Structure:**
bronze/
├── indodax/
│   ├── dataset=pairs/
│   └── dataset=summaries/
├── postgresql/
│   ├── dataset=users/
│   └── ...
└── mongodb/
    └── dataset=user_events/

### DuckDB for Local Development

**Configuration:**
outputs:
  dev:
    type: duckdb
    path: data/warehouse/indodax.duckdb

### Databricks for Production

**Configuration:**
outputs:
  prod:
    type: databricks
    catalog: crypto_platform
    schema: marts

## Testing Strategy

### Unit Tests

**Ingestion Framework:**
- Import validation
- Watermark manager tests
- Client instantiation

### Integration Tests

**dbt Models:**
- Model existence
- Schema validation
- Intermediate models

**Airflow DAGs:**
- DAG syntax
- Content validation
- Schedule configuration

## Failure Handling

### Extraction Failures

**Retry Policy:**
- 3 attempts (exponential backoff)
- Graceful failure if retries exhausted
- Watermark NOT updated on failure

### Bronze Write Failures

**Atomic Writes:**
- Temp file + rename pattern
- Rollback on failure
- No partial writes

### dbt Failures

**Testing:**
- not_null, unique constraints
- Business rules (singular tests)
- Failures block downstream tasks

## Monitoring & Observability

### Logging

**Structured format:**
logger.info("source=%s, dataset=%s, rows=%d, watermark_before=%s, watermark_after=%s", ...)

### Metrics

**Airflow:**
- Task duration
- Retry counts
- DAG run status

**dbt:**
- Model runtime
- Test failures
- Row counts

## Security Considerations

### Secrets Management

- Environment variables only
- Never commit to Git
- .env in .gitignore

### Access Control

- MinIO bucket policies
- Databricks schema access
- PostgreSQL row-level security (future)

## Future Enhancements

1. CI/CD: GitHub Actions for automated testing
2. Monitoring: Alerting on pipeline failures
3. Data Lineage: dbt docs for documentation
4. User Analytics: Enhanced user behavior tracking
5. ML Features: Feature store for trading signals
