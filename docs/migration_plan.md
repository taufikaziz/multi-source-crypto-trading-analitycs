# Migration Plan — Indodax Market Data -> Multi-Source Crypto Platform

Reference: `workflow.md`. Strategy: **audit -> reuse -> refactor -> extend -> migrate -> integrate -> test**
(no big-bang rewrite). Existing app is the starting point.

## A. Existing Architecture (as-is, verified on disk)

```
                 Indodax API          PostgreSQL(app)      MongoDB
                     | async HTTP          asyncpg             motor
                     v                       |                     |
            src/ingestion/indodax_client  src/ingestion/postgres  src/ingestion/mongodb
                     |                       |                     |
            src/ingestion/{base,retry,models,watermark} (shared async framework)
                     | gather (parallel extraction per source)
                     v
            src/bronze/writer.py (BronzeWriter) + src/storage/minio.py
              local FS fallback  |  MinIO (default)  <- JSON for ALL sources
                     |
          (watermark commit AFTER Bronze write -> src/ingestion/watermark.py -> PostgreSQL etl_watermark)

Python pipeline (legacy/local, runnable via run_local.py):
  src/silver/transformer.py  -> build_market_snapshot (pandas)
  src/gold/transformer.py    -> build_market_metrics  (pandas)
  src/quality/{silver,gold}_checks.py -> validation
  src/warehouse/loader.py    -> DuckDB WarehouseLoader (local)
  src/warehouse/databricks_loader.py -> DatabricksWarehouseLoader (fact dims)

Orchestrated path (Airflow DAG: airflow-docker/dags/indodax_market_pipeline.py):
  extract_indodax | extract_postgresql | extract_mongodb   (parallel)
       | write Bronze to MinIO (postgres/mongo) + commit watermarks
  load_bronze_to_databricks -> src/warehouse/bronze_databricks.py (run_bronze_load)
       | populates Databricks tables: <catalog>.bronze.{pairs,summaries,users,orders,...}
  dbt_build_warehouse -> dbt_crypto_platform/ dbt build --target prod
       | staging -> intermediate -> marts -> <catalog>.marts.gold_*
```

Key observations:
- Async ingestion framework, MinIO Bronze, dbt project, Airflow DAG, DuckDB local dev all ALREADY built.
- Gold/business-metrics logic EXISTS TWICE: (a) Python `src/gold/transformer.py` + `databricks_loader.py`, (b) dbt marts in `dbt_crypto_platform/models/marts/`. Per workflow.md the dbt marts are the target Gold layer.
- The DAG does NOT call Python Silver/Gold; it relies on `run_bronze_load` -> dbt. So the Python Silver/Gold/Databricks-warehouse-loader are effectively DEPRECATED by the DAG path (kept only for `run_local.py` / local DuckDB dev).

## B. Target Architecture (workflow.md §2, §34)

```
Indodax API        PostgreSQL        MongoDB
      | async HTTP / asyncpg / Motor
      v
Async Ingestion  (src/ingestion/*, asyncio.gather)
      v
MinIO Bronze (s3://indodax-data/bronze/{source}/{dataset}/ingestion_date=Y-M-D/hour=H/)
      - Indodax pairs/summaries : JSON  (raw API fidelity)
      - PostgreSQL tables        : Parquet (tabular, replayable)
      - MongoDB user_events      : JSON  (raw envelope)
      v
dbt Staging  (dbt_crypto_platform/models/staging/...)   rename/cast/clean/dedup
      v
dbt Intermediate (.../intermediate/...)   join/enrich
      v
dbt Marts / Gold (.../marts/{market,trading,activity,business})
      v
Databricks SQL Warehouse (crypto_platform.marts.*)
      v
Analytics / BI
Airflow 3 orchestrates; Databricks is external compute.
Local dev (8GB RAM): dbt-duckdb vs local DuckDB files; Databricks only for prod evidence.
```

## C. Migration Matrix

| Existing Component | Target Component | Action | Reason |
|---|---|---|---|
| src/ingestion/* (async framework) | Async ingestion layer | KEEP/REFACTOR | Already implements Phase 5-8, 10-11; reuse. Verify retry/timeout aligns with §18. |
| src/bronze/writer.py + src/storage/minio.py | MinIO Bronze (Phase 9) | REFACTOR | Correct MinIO-first. Fix: write PostgreSQL extracts as Parquet (§9), keep Indodax+Mongo as JSON. |
| src/silver/transformer.py (Python) | dbt staging/indodax (stg_indodax__pairs/summaries) | MIGRATE | §11 staging = rename/cast/standardize. dbt already has these models. Move logic; keep Python only for pre-storage validation. |
| src/gold/transformer.py (build_market_metrics) | dbt marts gold_market_daily etc. | MIGRATE | §13 marts = business metrics. Logic already modelled in dbt_crypto_platform marts. Deprecate Python gold. |
| src/quality/{silver,gold}_checks.py | dbt tests (generic + singular) | MIGRATE | §14. dbt already has 6 singular tests. Extend coverage there; remove Python checks from orchestrated path. |
| src/warehouse/loader.py + schema.py + connection.py (DuckDB) | Local dbt-duckdb dev target | KEEP | §10/15 dev = DuckDB. Used by profiles.yml `dev`. |
| src/warehouse/databricks_loader.py | n/a (replaced by dbt marts) | DEPRECATE | Loads Gold fact tables directly; duplicates dbt marts. DAG/Prod uses dbt marts. |
| src/warehouse/bronze_databricks.py (run_bronze_load) | Bronze->Databricks bridge | FIX+MOVE to src/ | Feeds dbt sources. **Fix bug:** read Indodax bronze from MinIO, not local disk. Consider promoting scripts/load_bronze_databricks.py duplicate into this module. |
| src/orchestration/pipeline.py (run_pipeline, Python B->S->G->DuckDB) | n/a | DEPRECATE | Superseded by DAG + dbt. Keep only as local-standalone reference if useful. |
| src/orchestration/tasks.py | Airflow task entry points | REFACTOR | Keep ingestion/bronze/watermark helpers used by DAG. Drop Silver/Gold/warehouse functions the DAG no longer uses (or mark deprecated). |
| airflow-docker/dags/indodax_market_pipeline.py | Airflow 3 DAG (Phase 16) | FIX/REFACTOR | Flow already correct. Fix run_bronze_load bug + ensure deterministic object keys (§19). Add ruff/lint in CI. |
| dbt_crypto_platform/ | dbt transformation layer (Phase 10-14) | KEEP/EXTEND | Staging/intermediate/marts + tests present. Validate source wiring to bronze tables; add generic tests. |
| .env.example / airflow-docker/.env | Env/config (Phase 24) | FIX docs | Correct PYTHONPATH = /opt/airflow (parent of mounted src). Remove /opt/airflow/src references. |
| tests/ (flat) | tests/{unit,integration,data_quality} (§21) | REFACTOR | Reorganize; fill test_indodax_client.py; add integration tests for MinIO write, dbt build vs DuckDB. |
| .github/workflows/ci.yml | CI (§23) | EXTEND | Add ruff, dbt build vs DuckDB fixtures + dbt test. Keep PR-cheap. |

## D. Final Project Structure (proposed, realistic for 8GB RAM)

```
indodax-market-data/
  src/
    ingestion/      # async framework (keep)
    storage/        # minio abstraction (refactor: parquet for PG)
    bronze/         # BronzeWriter (keep)
    silver/         # DEPRECATED (migrated to dbt staging)
    gold/           # DEPRECATED (migrated to dbt marts)
    quality/        # DEPRECATED from orchestrated path (dbt tests take over)
    warehouse/
      connection.py   # DuckDB local  (keep)
      schema.py       # DuckDB schema (keep)
      loader.py       # DuckDB loader (keep for local)
      bronze_databricks.py  # FIX (read MinIO) + MOVE from scripts/
      databricks_loader.py  # DEPRECATE (dbt marts own Gold)
    orchestration/
      tasks.py       # Airflow entry points (refactor: drop unused S/G funcs)
      pipeline.py    # DEPRECATED (legacy local path)
  dbt_crypto_platform/   # dbt: staging/intermediate/marts + tests (target transformation layer)
  airflow-docker/         # Docker + DAG
    dags/indodax_market_pipeline.py
    docker-compose.yml / Dockerfile
    .env
  infra/                 # postgres/mongo seeds + init
  scripts/               # synthetic data generators + bronze-load CLI wrappers
  tests/                 # unit | integration | data_quality
  docs/                  # audit, contracts, plan, failure_testing (workflow.md §25)
  .env.example / workflow.md / AGENTS.md / ROADMAP.md
```

## E. Phase Plan (condensed, workflow.md numbering)

0. Audit (this doc) + business requirements + data contracts (Bronze/Silver/Gold). -> docs/
1. Business requirements -> docs/business_requirements.md (6 questions -> sources/cols/Gold model).
2. Data contracts first (Bronze/Silver/Gold) BEFORE transformation.
3. (Infra/data already present) seed synthetic data; validate ingestion seeds exist.
4. Docker infra (already present): ensure postgres-app seed + Mongo init.
5-11. Async ingestion (mostly DONE) -> dbt staging (DONE, verify) -> intermediate -> marts.
12. Storage migration: Postgres Bronze Parquet; keep Indodax/Mongo JSON. Already on MinIO.
13. dbt marts / Gold (DONE models; validate output vs Python gold).
14. Data quality: dbt tests (extend 6 singular -> generic too).
15. Databricks prod target (profiles.yml prod; env vars).
16-18. Airflow 3 (DONE) + async + retries/timeouts.
19. Idempotency (deterministic keys, run_id).
20. Structured logging (DONE in tasks.py; adopt project-wide).
21. Tests (reorganize + integration).
22. Failure testing (docs/failure_testing.md).
23. CI (ruff + dbt build/verify vs DuckDB).
24. Security/config (.env.example).
25. Docs (§25 list).
26. Portfolio evidence.

## F. Risk Register (abbreviated, workflow.md §31 + §30)

- breaking existing app: mitigate by preserving Python legacy path locally & tests green (57 pass) during migration.
- duplicate data: dedup via deterministic object keys + run_id + dbt unique keys (§19).
- watermark corruption: commit ONLY after Bronze verified (§8) — current code already does; guard re-extract idempotency.
- MinIO failure: retry + healthcheck present; add MinIO write verification step.
- dbt failure: minimal retries, fail fast (§18); dbt build returns non-zero (✓).
- Databricks connection failure: token auth via env var (✓); fallback oauth for interactive local only.
- Airflow retry: extraction 3x exp backoff (✓), dbt 1x (✓).
- schema drift: contract-first (Bronze/Silver/Gold) + dbt tests.
- resource exhaustion (8GB): LocalExecutor, DuckDB local, Databricks external; no Spark/Kafka/Celery.
- **NEW CRITICAL:** DAG fails at `load_bronze_to_databricks` because Bronze Indodax is in MinIO but `run_bronze_load` reads local disk -> SystemExit. Must fix before any end-to-end DAG success.

## G. Phase 0 — concrete next steps

1. This audit (`docs/audit.md`) + this plan (`docs/migration_plan.md`) are done.
2. Next: Phase 0 verification — run `pytest` (57 pass) + `dbt parse` to confirm toolchain.
3. Then choose first concrete fix: the Phase 12 bug above (MinIO read in bronze_databricks), or Phase 1 Bronze-contract (Postgres Parquet), or start Phase 1 (business_requirements.md).

Recommend: fix the pipeline-breaking DAG bug first (it blocks "Airflow DAG success" portfolio evidence), then document contracts.
