"""Databricks Load DAG - Loads Gold data to Databricks."""

from datetime import datetime, timedelta

from airflow.sdk import dag, task

@dag(
    dag_id="databricks_load",
    start_date=datetime(2026, 9, 12),
    schedule=["s3://indodax-data/dbt/"],
    catchup=False,
    max_active_runs=1,
    tags=["databricks", "warehouse"],
)
def databricks_load():
    """DAG untuk load ke Databricks."""

    @task(
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
    def load_to_databricks():
        """Load Gold data to Databricks SQL Warehouse."""
        from src.warehouse.databricks_loader import DatabricksWarehouseLoader
        import pandas as pd
        import duckdb
        
        # Load Gold data from DuckDB
        conn = duckdb.connect("data/warehouse/indodax.duckdb")
        gold_df = conn.execute("SELECT * FROM gold_crypto_business_metrics").fetchdf()
        conn.close()
        
        # Load to Databricks
        loader = DatabricksWarehouseLoader()
        loader.load_market_snapshot(gold_df)

    load_to_databricks()

databricks_load()
