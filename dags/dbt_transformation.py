"""dbt Transformation DAG - Runs dbt models to Silver and Gold."""

from datetime import datetime, timedelta

import os

from airflow.sdk import dag, task

DBT_PROJECT_DIR = os.getenv(
    "DBT_PROJECT_DIR", "/opt/airflow/dbt_crypto_platform"
)

@dag(
    dag_id="dbt_transformation",
    start_date=datetime(2026, 9, 12),
    schedule=["s3://indodax-data/bronze/"],
    catchup=False,
    max_active_runs=1,
    tags=["dbt", "silver", "gold"],
)
def dbt_transformation():
    """DAG untuk dbt transformation."""

    @task(
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
    def run_dbt_build():
        """Run dbt build (staging + intermediate + marts)."""
        import subprocess
        result = subprocess.run(
            ["dbt", "build", "--target", "prod",
                "--project-dir", DBT_PROJECT_DIR,
                "--profiles-dir", DBT_PROJECT_DIR],
            capture_output=True,
            text=True,
            cwd=DBT_PROJECT_DIR
        )
        if result.returncode != 0:
            raise Exception(f"dbt build failed: {result.stderr}")
        return result.stdout

    run_dbt_build()

dbt_transformation()
