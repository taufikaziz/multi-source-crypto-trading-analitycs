import asyncio, logging, os, sys
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

os.environ.setdefault("POSTGRES_APP_DSN", "postgresql://postgres:postgres@localhost:5433/indodax")
os.environ.setdefault("MONGODB_URI", "mongodb://mongodb:Mongodbxyz@localhost:27017/indodax?authSource=admin")
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("MINIO_ROOT_USER", "minioadmin")
os.environ.setdefault("MINIO_ROOT_PASSWORD", "minioadmin")
os.environ.setdefault("MINIO_BUCKET", "indodax-data")
os.environ.setdefault("BRONZE_STORAGE_BACKEND", "minio")
os.environ.setdefault("BRONZE_MINIO_BASE_PATH", "bronze")
os.environ.setdefault("DATABRICKS_SERVER_HOSTNAME", "dbc-400e8cf7-6e57.cloud.databricks.com")
os.environ.setdefault("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/c045710ab07b325b")
os.environ.setdefault("DATABRICKS_TOKEN", "REPLACE_WITH_DATABRICKS_TOKEN")
os.environ.setdefault("DATABRICKS_CATALOG", "workspace")

from src.orchestration.pipeline import run_pipeline
asyncio.run(run_pipeline())
print("PIPELINE DONE OK")
