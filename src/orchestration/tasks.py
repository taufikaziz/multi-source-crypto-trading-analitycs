import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.bronze.writer import BronzeWriter
from src.gold.transformer import build_market_metrics
from src.gold.writer import GoldWriter
from src.ingestion.indodax_client import IndodaxClient
from src.ingestion.models import ExtractionMetadata, new_run_id
from src.ingestion.mongodb import MongoDBExtractor
from src.ingestion.postgres import PostgresExtractor
from src.ingestion.watermark import WatermarkManager
from src.quality.gold_checks import validate_market_metrics
from src.quality.silver_checks import validate_market_snapshot
from src.silver.transformer import build_market_snapshot
from src.silver.writer import SilverWriter
from src.warehouse.databricks_loader import DatabricksWarehouseLoader

logger = logging.getLogger(__name__)


def create_run_context() -> dict:
    """Create metadata shared across one pipeline run."""
    captured_at = datetime.now(timezone.utc)
    run_id = captured_at.strftime("%Y%m%dT%H%M%SZ")
    return {"captured_at": captured_at, "run_id": run_id}


async def ingest_indodax_data(run_id: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch pairs and summaries from Indodax concurrently.
    Emits structured metadata logging for observability.
    """
    current_run_id = run_id or new_run_id()
    start_time = datetime.now(timezone.utc)
    client = IndodaxClient()

    meta = ExtractionMetadata(
        run_id=current_run_id,
        source="indodax",
        dataset="market_data",
        start_time=start_time,
    )

    try:
        pairs, summaries = await client.fetch_all()
        rows = len(pairs) + len(summaries.get("tickers", {}))
        meta.finish(status="success", rows=rows)
        logger.info(
            "run_id=%s source=indodax dataset=market_data rows=%d duration=%.2fs status=success",
            meta.run_id,
            meta.rows_extracted,
            meta.duration_s,
        )
        return pairs, summaries
    except Exception as exc:
        meta.finish(status="failed", error=str(exc))
        logger.error(
            "run_id=%s source=indodax dataset=market_data error=%s duration=%.2fs status=failed",
            meta.run_id,
            meta.error,
            meta.duration_s,
        )
        raise


async def write_bronze_data(
    pairs: list,
    summaries: dict,
    captured_at: datetime,
) -> tuple[str, str]:
    """
    Write pairs and summaries JSON files concurrently to Bronze.
    Both writes are independent so they run in parallel.
    """
    writer = BronzeWriter()
    paths = await writer.write_many(
        datasets={"pairs": pairs, "summaries": summaries},
        captured_at=captured_at,
    )
    return str(paths["pairs"]), str(paths["summaries"])


def transform_silver_data(
    pairs: list,
    summaries: dict,
    captured_at: datetime,
    summaries_path: str,
    run_id: str,
) -> pd.DataFrame:
    """
    CPU-bound pandas transform — intentionally synchronous.
    asyncio provides no benefit here; blocking the event loop briefly
    is acceptable for a pure in-memory computation.
    """
    return build_market_snapshot(
        pairs=pairs,
        summaries=summaries,
        captured_at=captured_at,
        source_file=summaries_path,
        run_id=run_id,
    )


def validate_silver_data(dataframe: pd.DataFrame) -> None:
    """Synchronous quality check — pure CPU, no I/O."""
    validate_market_snapshot(dataframe=dataframe)
    logger.info("Silver data quality validation passed.")


async def write_silver_data(
    dataframe: pd.DataFrame,
    captured_at: datetime,
    run_id: str,
) -> str:
    """Write Silver Parquet file asynchronously."""
    writer = SilverWriter()
    path = await writer.write_market_snapshot(
        dataframe=dataframe,
        ingestion_date=captured_at.strftime("%Y-%m-%d"),
        hour=captured_at.strftime("%H"),
        run_id=run_id,
    )
    return str(path)


def transform_gold_data(dataframe: pd.DataFrame) -> pd.DataFrame:
    """CPU-bound pandas transform — intentionally synchronous."""
    return build_market_metrics(dataframe=dataframe)


def validate_gold_data(dataframe: pd.DataFrame) -> None:
    """Synchronous quality check — pure CPU, no I/O."""
    validate_market_metrics(dataframe=dataframe)
    logger.info("Gold data quality validation passed.")


async def write_gold_data(
    dataframe: pd.DataFrame,
    captured_at: datetime,
    run_id: str,
) -> str:
    """Write Gold Parquet file asynchronously."""
    writer = GoldWriter()
    path = await writer.write_market_metrics(
        dataframe=dataframe,
        ingestion_date=captured_at.strftime("%Y-%m-%d"),
        hour=captured_at.strftime("%H"),
        run_id=run_id,
    )
    return str(path)


async def load_data_warehouse(dataframe: pd.DataFrame) -> None:
    """
    Load Gold data into Databricks.
    The databricks-sql-connector is blocking-only — offload to a thread
    executor so it does not stall the event loop.
    """
    loop = asyncio.get_running_loop()
    loader = DatabricksWarehouseLoader()

    await loop.run_in_executor(
        None,
        loader.load_market_snapshot,
        dataframe,
    )

    logger.info("Databricks Warehouse load completed successfully.")


# ---------------------------------------------------------------------------
# MULTI-SOURCE INGESTION (Phase 7 + Phase 8 + Phase 20)
# PostgreSQL + MongoDB extractors with watermark-based incremental
# extraction. Structured audit metadata & logging for every dataset.
# ---------------------------------------------------------------------------

POSTGRES_SOURCE = "postgres"
POSTGRES_DATASETS = (
    ("users", "updated_at"),
    ("accounts", "updated_at"),
    ("assets", "created_at"),
    ("orders", "updated_at"),
    ("trades", "executed_at"),
    ("transactions", "created_at"),
)

MONGO_SOURCE = "mongodb"
MONGO_DATASETS = (
    "tickers",
    "orderbooks",
    "user_events",
)


def postgres_app_dsn() -> str:
    explicit = os.getenv("POSTGRES_APP_DSN")
    if explicit:
        return explicit
    user = os.getenv("POSTGRES_APP_USER", os.getenv("POSTGRES_USER", "postgres"))
    password = os.getenv("POSTGRES_APP_PASSWORD", os.getenv("POSTGRES_PASSWORD", "postgres"))
    host = os.getenv("POSTGRES_APP_HOST", "postgres-app")
    port = os.getenv("POSTGRES_APP_PORT", "5432")
    db = os.getenv("POSTGRES_APP_DB", "indodax")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def mongo_connection() -> tuple[str, str]:
    uri = os.getenv(
        "MONGODB_URI",
        "mongodb://mongodb:Mongodbxyz@mongodb:27017/indodax?authSource=admin",
    )
    database = os.getenv("MONGO_DATABASE", "indodax")
    return uri, database


async def _extract_postgres_table(
    dsn: str,
    table: str,
    watermark_column: str,
    last_watermark,
    run_id: str,
) -> Tuple[str, List[Dict[str, Any]], Optional[datetime], ExtractionMetadata]:
    start_time = datetime.now(timezone.utc)
    meta = ExtractionMetadata(
        run_id=run_id,
        source="postgres",
        dataset=table,
        start_time=start_time,
        watermark_before=last_watermark,
    )

    extractor = PostgresExtractor(
        conn_string=dsn,
        table=table,
        watermark_column=watermark_column,
        namespace=f"postgresql.{table}",
    )
    await extractor.connect()
    try:
        data, max_watermark = await extractor.extract(last_watermark)
        meta.finish(
            status="success",
            rows=len(data),
            watermark_after=max_watermark if data else last_watermark,
        )
        return table, data, max_watermark, meta
    except Exception as exc:
        meta.finish(status="failed", error=str(exc))
        logger.error(
            "run_id=%s source=postgres dataset=%s error=%s status=failed",
            run_id, table, str(exc),
        )
        raise
    finally:
        await extractor.close()


async def extract_postgres_data(run_id: Optional[str] = None) -> tuple[dict, dict]:
    current_run_id = run_id or new_run_id()
    dsn = postgres_app_dsn()
    manager = WatermarkManager(conn_string=dsn)
    await manager.connect()
    try:
        stored = await manager.get_all_watermarks()
        results = await asyncio.gather(
            *[
                _extract_postgres_table(
                    dsn,
                    table,
                    column,
                    stored.get(f"postgresql.{table}"),
                    current_run_id,
                )
                for table, column in POSTGRES_DATASETS
            ]
        )
    finally:
        await manager.close()

    datasets, watermarks = {}, {}
    for table, data, max_watermark, meta in results:
        namespace = f"postgresql.{table}"
        logger.info(
            "run_id=%s source=postgres dataset=%s rows=%d watermark_before=%s watermark_after=%s duration=%.2fs status=%s",
            meta.run_id,
            meta.dataset,
            meta.rows_extracted,
            meta.watermark_before,
            meta.watermark_after,
            meta.duration_s,
            meta.status,
        )
        if not data:
            continue
        datasets[table] = data
        watermarks[namespace] = max_watermark
    return datasets, watermarks


async def _extract_mongo_collection(
    uri: str,
    database: str,
    collection: str,
    last_watermark,
    run_id: str,
) -> Tuple[str, List[Dict[str, Any]], Optional[datetime], ExtractionMetadata]:
    start_time = datetime.now(timezone.utc)
    meta = ExtractionMetadata(
        run_id=run_id,
        source="mongodb",
        dataset=collection,
        start_time=start_time,
        watermark_before=last_watermark,
    )

    extractor = MongoDBExtractor(
        uri=uri,
        database=database,
        collection=collection,
        namespace=f"mongodb.{collection}",
    )
    await extractor.connect()
    try:
        data, max_watermark = await extractor.extract(last_watermark)
        meta.finish(
            status="success",
            rows=len(data),
            watermark_after=max_watermark if data else last_watermark,
        )
        return collection, data, max_watermark, meta
    except Exception as exc:
        meta.finish(status="failed", error=str(exc))
        logger.error(
            "run_id=%s source=mongodb dataset=%s error=%s status=failed",
            run_id, collection, str(exc),
        )
        raise
    finally:
        await extractor.close()


async def extract_mongodb_data(run_id: Optional[str] = None) -> tuple[dict, dict]:
    current_run_id = run_id or new_run_id()
    uri, database = mongo_connection()
    dsn = postgres_app_dsn()
    manager = WatermarkManager(conn_string=dsn)
    await manager.connect()
    try:
        stored = await manager.get_all_watermarks()
        results = await asyncio.gather(
            *[
                _extract_mongo_collection(
                    uri,
                    database,
                    collection,
                    stored.get(f"mongodb.{collection}"),
                    current_run_id,
                )
                for collection in MONGO_DATASETS
            ]
        )
    finally:
        await manager.close()

    datasets, watermarks = {}, {}
    for collection, data, max_watermark, meta in results:
        namespace = f"mongodb.{collection}"
        logger.info(
            "run_id=%s source=mongodb dataset=%s rows=%d watermark_before=%s watermark_after=%s duration=%.2fs status=%s",
            meta.run_id,
            meta.dataset,
            meta.rows_extracted,
            meta.watermark_before,
            meta.watermark_after,
            meta.duration_s,
            meta.status,
        )
        if not data:
            continue
        datasets[collection] = data
        watermarks[namespace] = max_watermark
    return datasets, watermarks


async def write_source_bronze_data(
    source: str,
    datasets: dict,
    captured_at: datetime,
) -> dict:
    if not datasets:
        logger.info("source=%s: no new rows, skipping Bronze write", source)
        return {}
    writer = BronzeWriter()
    paths = await writer.write_many(
        datasets=datasets,
        captured_at=captured_at,
        source=source,
    )
    return {name: str(path) for name, path in paths.items()}


async def commit_source_watermarks(
    source: str,
    watermarks: dict,
) -> None:
    if not watermarks:
        return
    manager = WatermarkManager(conn_string=postgres_app_dsn())
    await manager.connect()
    try:
        await manager.commit_watermarks(watermarks, source)
    finally:
        await manager.close()
    for namespace, watermark in watermarks.items():
        logger.info(
            "source=%s namespace=%s watermark_after=%s status=committed",
            source, namespace, watermark,
        )
