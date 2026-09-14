"""Async Ingestion DAG - Extracts data from all sources to Bronze."""

from datetime import datetime, timedelta
import asyncio

from airflow.sdk import dag, task

INGESTION_OUTPUT = "s3://indodax-data/bronze/"

@dag(
    dag_id="crypto_ingestion",
    start_date=datetime(2026, 9, 12),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["ingestion", "bronze"],
)
def crypto_ingestion():
    """DAG untuk extraction semua source ke Bronze layer."""

    @task(
        retries=3,
        retry_delay=timedelta(minutes=5),
    )
    def extract_all_sources():
        """Run async extraction dari semua source."""
        from src.ingestion.pipeline import run_async_ingestion
        asyncio.run(run_async_ingestion())

    extract_all_sources()

crypto_ingestion()
