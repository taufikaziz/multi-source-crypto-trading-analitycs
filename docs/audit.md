# Data Engineering Audit — Indodax Market Data (existing -> workflow.md target)

Source of truth for "workflow": `workflow.md` (root). It defines a phased build of a
multi-source crypto analytics platform: async ingestion (aiohttp/asyncpg/Motor) ->
MinIO Bronze -> dbt (staging/intermediate/marts) -> Databricks -> Airflow 3 orchestration.

This audit maps what **already exists** on disk to the target, and decides
KEEP / REFACTOR / MIGRATE / DEPRECATE / REMOVE for each component.

Legend: K=KEEP, R=REFACTOR, M=MIGRATE TO DBT, D=DEPRECATE, X=REPLACE, rm=REMOVE.

## 1. Existing components

| # | Component | File(s) | Exists? | workflow.md phase target | Decision | Reason |
|---|-----------|---------|---------|--------------------------|----------|--------|
| 1 | Indodax API client | src/ingestion/indodax_client.py | K | Phase 5/6 (async ingestion) | R | Already async (aiohttp), 429/5xx retry. Reuse as-is; keep under ingestion package. |
| 2 | Ingestion base + clients | src/ingestion/{base,indodax,postgres,mongodb,retry,models,watermark}.py | K | Phase 5-8 | R/K | Full async framework already built (asyncio.gather, retry, watermark). Reuse; small fixes only. |
| 3 | Postgres extractor | src/ingestion/postgres.py | K | Phase 5/7 | K | Incremental via watermark_column. OK. |
| 4 | Mongo extractor | src/ingestion/mongodb.py | K | Phase 5/7 | K | Incremental via ingested_at. OK. |
| 5 | Watermark manager | src/ingestion/watermark.py | K | Phase 7/8 | K | Commits AFTER Bronze write (Phase 8 safe ordering). OK. |
| 6 | Bronze writer | src/bronze/writer.py + src/storage/minio.py | K | Phase 9 | K* | MinIO-first + local fallback. **Drift:** writes ALL sources as JSON; workflow.md Phase 9 says tabular DB extracts should be Parquet. Needs format-per-source. |
| 7 | Silver transform (Python) | src/silver/transformer.py | K | Phase 11 (dbt staging) | M/D | build_market_snapshot parses Indodax JSON -> row. Logic to move to `dbt staging/indodax`. Keep Python only for pre-storage validation if useful. |
| 8 | Gold transform (Python) | src/gold/transformer.py | K | Phase 13 (dbt marts) | M/D | build_market_metrics (24h/7d change, spread, volume_rank) -> dbt marts (gold_market_daily etc). Deprecate Python gold. |
| 9 | Quality checks (Python) | src/quality/{silver,gold}_checks.py | K | Phase 14 (dbt tests) | M/D | Move analytical tests to dbt (generic + singular). Keep Python checks as pre-Bronze validation only. |
| 10 | DuckDB warehouse loader | src/warehouse/{loader,schema,connection}.py | K | Phase 10/15 (local dbt dev) | K | DuckDB local = dbt-duckdb dev target (profiles.yml `dev`). Keep for local/testing. |
| 11 | Databricks gold loader | src/warehouse/databricks_loader.py | K | Phase 15 (marts via dbt) | D | Loads Gold fact tables directly. Overlaps dbt marts. The orchestrated DAG does NOT use this; dbt builds Gold. Deprecate — let dbt own Gold. |
| 12 | Bronze -> Databricks loader | src/warehouse/bronze_databricks.py | K | Phase 13/15 | R | Creates Databricks `bronze.*` tables that dbt sources read. **BUG:** `load_indodax` reads Bronze from local `data/bronze` (SystemExit), but DAG writes Indodax Bronze to MinIO. Must read from MinIO (s3). |
| 13 | Orchestration tasks | src/orchestration/{tasks,pipeline}.py | K | Phase 5/7/8/20 | R | tasks.py used by DAG (ingest/write_bronze/extract_pg_mongo/commit_watermark/load_data_warehouse). pipeline.py `run_pipeline()` = legacy Indodax-only Python B->S->G path (not used by DAG). Reconcile: DAG should be the single orchestrated path. |
| 14 | Airflow DAG | airflow-docker/dags/indodax_market_pipeline.py | K | Phase 16 | R | Flow extract -> MinIO Bronze -> Databricks -> dbt build -> END matches Phase 16/34. **Fix** load_bronze_to_databricks (bug #12) + dependency wiring. |
| 15 | dbt project | dbt_crypto_platform/{models,macros,packages.yml,profiles.yml} | K | Phase 10-13/14 | K/E | staging(indodax/postgres/mongodb), intermediate, marts{market,trading,activity,business}, 6 singular tests, dbt_utils/codegen packages. Complete & aligned. Verify sources resolve to Databricks bronze tables. |
| 16 | Synthetic data | scripts/generate_synthetic_{postgres,mongodb}.py, seed_postgres.sql, infra/mongodb/init/... | K | Phase 3 (data seeds) | K | Present. |
| 17 | Docker | airflow-docker/{docker-compose,Dockerfile}.yml | K | Phase 4 | K | Postgres-app, Mongo, Minio, Airflow 3 (api/scheduler/dag-processor), LocalExecutor. duckdb + boto3 in image. No Databricks in Docker (external). OK. |
| 18 | Env config | .env.example, airflow-docker/.env | K | Phase 24 | R | **Drift:** AGENTS.md/.env.backup say PYTHONPATH=/opt/airflow/src (wrong). Correct value is /opt/airflow (parent of `src` package, given mount `../src:/opt/airflow/src`). Fix docs. |
| 19 | Tests | tests/*.py (flat) | K | Phase 21 | R | 57 pass (silver/gold transformer, quality checks, warehouse loader). Empty test_indodax_client.py. Reorganize into tests/unit|integration|data_quality. |
| 20 | CI | .github/workflows/ci.yml | K | Phase 23 | E | Runs pytest + dbt parse only. Missing: ruff lint, dbt build vs DuckDB fixtures, dbt test. Extend. |

## 2. Data flow mapping (current vs target)

Target (workflow.md §34):
  Sources -> async ingestion -> MinIO Bronze -> dbt staging -> dbt intermediate
          -> dbt marts/gold -> Databricks -> BI
              (Airflow 3 orchestrates)

Current:
  - Async ingestion framework: DONE (src/ingestion/*)
  - MinIO Bronze: DONE (BronzeWriter, default minio) but format/JSON drift for Postgres
  - dbt staging/intermediate/marts: DONE (dbt_crypto_platform), sources read `{{ source('bronze', ...) }}` = Databricks bronze tables populated by run_bronze_load
  - DAG orchestrates: extract -> MinIO Bronze -> run_bronze_load -> dbt build -> Databricks : STRUCTURE correct
  - Python Silver/Gold/warehouse: legacy/local path (run_local.py -> DuckDB). Not used by DAG.
