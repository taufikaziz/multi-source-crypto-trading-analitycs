"""
Crypto Market Data Pipeline DAG (Airflow 3)

Logical Flow:
                    ┌── extract_indodax ────┐
                    │                       │
start ─────────────┼── extract_postgresql ─┼──> load_bronze_to_databricks ──> dbt_build_warehouse ──> end
                    │                       │
                    └── extract_mongodb ────┘

Phase 16 & 18 Concurrency & Retry Policy:
- 3 extraction tasks run in parallel via Airflow scheduler.
- Extraction tasks: retries=3 with exponential backoff for transient network/DB errors.
- dbt / SQL tasks: minimal retries (retries=1) so logical/schema errors fail fast and stay visible.
- Bounded execution timeouts on all tasks.
- Pre-creates /tmp/dbt_logs and /tmp/dbt_target to ensure clean scheduled execution.
"""

import os
from datetime import datetime, timedelta

from airflow.sdk import dag, task

DBT_PROJECT_DIR = os.getenv("DBT_PROJECT_DIR", "/opt/airflow/dbt_crypto_platform")


@dag(
    dag_id="indodax_market_pipeline",
    start_date=datetime(2026, 8, 27),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=[
        "indodax",
        "market-data",
        "etl",
        "multi-source",
    ],
)
def indodax_market_pipeline():

    @task(
        retries=3,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=15),
        execution_timeout=timedelta(minutes=20),
    )
    def extract_indodax():
        """Extract Indodax API data (pairs & summaries) concurrently and write to MinIO Bronze."""
        import asyncio
        from datetime import datetime, timezone
        from src.orchestration.tasks import ingest_indodax_data, write_bronze_data

        async def _run():
            captured_at = datetime.now(timezone.utc)
            pairs, summaries = await ingest_indodax_data()
            pairs_path, summaries_path = await write_bronze_data(
                pairs=pairs,
                summaries=summaries,
                captured_at=captured_at,
            )
            return {"source": "indodax", "pairs": pairs_path, "summaries": summaries_path}

        return asyncio.run(_run())

    @task(
        retries=3,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=15),
        execution_timeout=timedelta(minutes=20),
    )
    def extract_postgresql():
        """Extract transactional tables incrementally from PostgreSQL, write to Bronze, commit watermarks."""
        import asyncio
        from datetime import datetime, timezone
        from src.orchestration.tasks import (
            extract_postgres_data,
            write_source_bronze_data,
            commit_source_watermarks,
        )

        async def _run():
            captured_at = datetime.now(timezone.utc)
            datasets, watermarks = await extract_postgres_data()
            paths = await write_source_bronze_data(
                source="postgresql",
                datasets=datasets,
                captured_at=captured_at,
            )
            await commit_source_watermarks(
                source="postgres",
                watermarks=watermarks,
            )
            return {"source": "postgresql", "paths": paths, "watermarks": {k: str(v) for k, v in watermarks.items()}}

        return asyncio.run(_run())

    @task(
        retries=3,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=15),
        execution_timeout=timedelta(minutes=20),
    )
    def extract_mongodb():
        """Extract event collections incrementally from MongoDB, write to Bronze, commit watermarks."""
        import asyncio
        from datetime import datetime, timezone
        from src.orchestration.tasks import (
            extract_mongodb_data,
            write_source_bronze_data,
            commit_source_watermarks,
        )

        async def _run():
            captured_at = datetime.now(timezone.utc)
            datasets, watermarks = await extract_mongodb_data()
            paths = await write_source_bronze_data(
                source="mongodb",
                datasets=datasets,
                captured_at=captured_at,
            )
            await commit_source_watermarks(
                source="mongodb",
                watermarks=watermarks,
            )
            return {"source": "mongodb", "paths": paths, "watermarks": {k: str(v) for k, v in watermarks.items()}}

        return asyncio.run(_run())

    @task(
        retries=2,
        retry_delay=timedelta(minutes=5),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=15),
        execution_timeout=timedelta(minutes=30),
    )
    def load_bronze_to_databricks(extract_results):
        """Copy Bronze sources (Postgres/Mongo/Indodax) to Databricks raw staging."""
        from src.warehouse.bronze_databricks import run_bronze_load

        counts = run_bronze_load()
        return counts

    @task(
        retries=1,
        retry_delay=timedelta(minutes=5),
        retry_exponential_backoff=False,
        execution_timeout=timedelta(minutes=60),
    )
    def dbt_build_warehouse(upstream):
        """Run dbt build (staging -> intermediate -> marts + tests) directly against Databricks."""
        import subprocess

        # Ensure temp directories exist for logging and compilation
        os.makedirs("/tmp/dbt_logs", exist_ok=True)
        os.makedirs("/tmp/dbt_target", exist_ok=True)

        result = subprocess.run(
            [
                "dbt",
                "build",
                "--target",
                "prod",
                "--project-dir",
                DBT_PROJECT_DIR,
                "--profiles-dir",
                DBT_PROJECT_DIR,
                "--log-path",
                "/tmp/dbt_logs",
                "--target-path",
                "/tmp/dbt_target",
            ],
            capture_output=True,
            text=True,
            cwd="/tmp",
        )
        if result.returncode != 0:
            raise RuntimeError(
                "dbt build --target prod failed:\n"
                + (result.stdout + result.stderr)[-4000:]
            )
        return result.stdout[-2000:]

    # Parallel extraction tasks
    indodax_extract = extract_indodax()
    postgres_extract = extract_postgresql()
    mongo_extract = extract_mongodb()

    # Sequential progression after parallel extraction completion
    warehouse_bronze = load_bronze_to_databricks([indodax_extract, postgres_extract, mongo_extract])
    marts = dbt_build_warehouse(warehouse_bronze)


indodax_market_pipeline()
