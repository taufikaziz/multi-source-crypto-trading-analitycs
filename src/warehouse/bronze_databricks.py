"""Load Bronze tables into Databricks (``<catalog>.bronze``).

Mirrors ``scripts/load_bronze_duckdb.py`` but writes to the Databricks SQL
Warehouse instead of the local DuckDB file, so ``dbt build --target prod``
can read its ``bronze.*`` sources directly from the warehouse.

Sources:
  - PostgreSQL tables are copied as-is.
  - MongoDB ``user_events`` keeps its raw envelope; ``context`` is stored
    as a JSON string and ``_id`` as text.
  - Indodax ``pairs``/``summaries`` JSON files are reshaped into the tabular
    bronze contract (same shaping as the DuckDB loader).

Configuration (environment variables, secrets via ``.env``):
  - ``DATABRICKS_SERVER_HOSTNAME``, ``DATABRICKS_HTTP_PATH``,
    ``DATABRICKS_TOKEN`` (required)
  - ``DATABRICKS_CATALOG`` (default: ``workspace``)
  - ``POSTGRES_APP_DSN`` or ``POSTGRES_USER``/``POSTGRES_PASSWORD``/
    ``POSTGRES_HOST`` (default host ``postgres`` = compose service name)
  - ``MONGODB_URI`` (default host ``mongodb``), ``MONGO_DATABASE``
  - ``BRONZE_BASE_PATH`` (default: ``data/bronze``) for Indodax JSON files

Usage:
    python scripts/load_bronze_databricks.py
"""

import glob
import json
from decimal import Decimal
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

CATALOG = os.getenv("DATABRICKS_CATALOG", "workspace")
BRONZE_SCHEMA = "bronze"

PG_TABLES_DDL = {
    "users": (
        "user_id STRING, email STRING, full_name STRING, "
        "is_active BOOLEAN, created_at TIMESTAMP, updated_at TIMESTAMP"
    ),
    "accounts": (
        "account_id STRING, user_id STRING, currency STRING, "
        "balance DECIMAL(18,8), locked_balance DECIMAL(18,8), "
        "created_at TIMESTAMP, updated_at TIMESTAMP"
    ),
    "assets": (
        "asset_id STRING, symbol STRING, name STRING, "
        "precision INT, created_at TIMESTAMP"
    ),
    "orders": (
        "order_id STRING, user_id STRING, pair STRING, order_type STRING, "
        "price DECIMAL(18,8), quantity DECIMAL(18,8), "
        "filled_quantity DECIMAL(18,8), status STRING, "
        "created_at TIMESTAMP, updated_at TIMESTAMP"
    ),
    "trades": (
        "trade_id STRING, order_id STRING, price DECIMAL(18,8), "
        "quantity DECIMAL(18,8), taker_side STRING, executed_at TIMESTAMP"
    ),
    "transactions": (
        "transaction_id STRING, account_id STRING, amount DECIMAL(18,8), "
        "type STRING, status STRING, created_at TIMESTAMP"
    ),
}

USER_EVENTS_DDL = (
    "_id STRING, event STRING, context STRING, ingested_at STRING"
)

PAIRS_DDL = (
    "pair STRING, ticker_id STRING, name STRING, base_currency STRING, "
    "quote_currency STRING, price_decimal_places INT, "
    "min_price DECIMAL(18,8), max_price DECIMAL(18,8), "
    "min_volume DECIMAL(18,8), created_at TIMESTAMP, run_id STRING"
)

SUMMARIES_DDL = (
    "pair STRING, last STRING, buy STRING, sell STRING, high STRING, "
    "low STRING, vol_coin STRING, vol_idr STRING, "
    "created_at TIMESTAMP, run_id STRING"
)


def _pg_dsn() -> str:
    explicit = os.getenv("POSTGRES_APP_DSN")
    if explicit:
        return explicit
    user = os.getenv("POSTGRES_USER", "airflow")
    password = os.getenv("POSTGRES_PASSWORD", "Airflowxyz")
    host = os.getenv("POSTGRES_HOST", "postgres")
    return "postgresql://{}:{}@{}:5432/indodax".format(user, password, host)


def _mongo_params() -> tuple:
    uri = os.getenv(
        "MONGODB_URI",
        "mongodb://mongodb:Mongodbxyz@mongodb:27017/indodax?authSource=admin",
    )
    database = os.getenv("MONGO_DATABASE", "indodax")
    return uri, database


def _bronze_base() -> Path:
    return Path(os.getenv("BRONZE_BASE_PATH", "data/bronze"))


def _table(name: str) -> str:
    return "{}.bronze.{}".format(CATALOG, name)


def _quoted(columns) -> str:
    return ", ".join("`{}`".format(c) for c in columns)


def _literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        return "'{}'".format(value.isoformat(sep=" "))
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    return "'{}'".format(text)


def _insert(cursor, table: str, columns, rows, chunk: int = 200) -> None:
    if not rows:
        logger.info("bronze table=%s: no rows, skipping insert", table)
        return
    for start in range(0, len(rows), chunk):
        values = ",".join(
            "(" + ",".join(_literal(v) for v in row) + ")"
            for row in rows[start:start + chunk]
        )
        cursor.execute(
            "INSERT INTO {} ({}) VALUES {}".format(
                table, _quoted(columns), values
            )
        )


def _replace_table(cursor, table: str, ddl: str) -> None:
    quoted_ddl = ", ".join(
        "`{}` {}".format(col.split(" ", 1)[0], col.split(" ", 1)[1])
        if " " in col else col
        for col in [c.strip() for c in ddl.split(",")]
    )
    cursor.execute("CREATE OR REPLACE TABLE {} ({})".format(table, quoted_ddl))


def load_postgres(cursor) -> dict:
    import psycopg2

    counts = {}
    pg_conn = psycopg2.connect(_pg_dsn())
    try:
        pg_cursor = pg_conn.cursor()
        for table, ddl in PG_TABLES_DDL.items():
            pg_cursor.execute("SELECT * FROM {}".format(table))
            columns = [d[0] for d in pg_cursor.description]
            rows = pg_cursor.fetchall()
            full = _table(table)
            _replace_table(cursor, full, ddl)
            _insert(cursor, full, columns, rows)
            counts[table] = len(rows)
            logger.info("bronze.%s: %d rows from postgres", table, len(rows))
    finally:
        pg_conn.close()
    return counts


def _as_text(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def load_mongo(cursor) -> dict:
    from pymongo import MongoClient

    uri, database = _mongo_params()
    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    try:
        docs = list(client[database].user_events.find())
    finally:
        client.close()
    rows = [
        (
            str(doc["_id"]),
            doc.get("event"),
            json.dumps(doc.get("context", {}), ensure_ascii=False),
            _as_text(doc.get("ingested_at")),
        )
        for doc in docs
    ]
    full = _table("user_events")
    _replace_table(cursor, full, USER_EVENTS_DDL)
    _insert(cursor, full, ["_id", "event", "context", "ingested_at"], rows)
    logger.info("bronze.user_events: %d docs from mongodb", len(rows))
    return {"user_events": len(rows)}


MINIO_BUCKET = os.getenv("MINIO_BUCKET", "indodax-data")
MINIO_PREFIX = os.getenv("BRONZE_MINIO_BASE_PATH", "bronze")


def _s3_client():
    """Build an S3 (MinIO) client using the same env config as BronzeWriter."""
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minioadmin"),
        aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
    )


def _load_latest_bronze(dataset: str, source: str = "indodax"):
    """Load the newest Bronze file for (source, dataset).

    Storage backend follows the same env config as src.bronze.BronzeWriter:
    BRONZE_STORAGE_BACKEND=minio (default) reads from MinIO/S3;
    BRONZE_STORAGE_BACKEND=local reads from the local filesystem.

    Returns (basename, parsed_json), e.g.
    ("pairs_20260824T000000Z.json", [...]).
    """
    if os.getenv("BRONZE_STORAGE_BACKEND", "minio") == "local":
        files = sorted(
            glob.glob(
                str(_bronze_base() / "source={}".format(source) / "dataset={}".format(dataset) / "**" / "*.json"),
                recursive=True,
            )
        )
        if not files:
            raise SystemExit("no bronze files for dataset={} (local)".format(dataset))
        path = Path(files[-1])
        return path.name, json.loads(path.read_text(encoding="utf-8"))

    client = _s3_client()
    prefix = "{}/{}/dataset={}/".format(MINIO_PREFIX, source, dataset)
    legacy_prefix = "{}/{}".format(MINIO_PREFIX, prefix)

    def _list_keys(search_prefix):
        found = []
        for page in client.get_paginator("list_objects_v2").paginate(
            Bucket=MINIO_BUCKET, Prefix=search_prefix
        ):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".json"):
                    found.append(obj["Key"])
        return found

    keys = _list_keys(prefix)
    if not keys:
        keys = _list_keys(legacy_prefix)
    if not keys:
        raise SystemExit(
            "no bronze files for dataset={} in s3://{}/{} (also checked s3://{}/{})".format(
                dataset, MINIO_BUCKET, prefix, MINIO_BUCKET, legacy_prefix
            )
        )
    keys.sort()
    key = keys[-1]
    body = client.get_object(Bucket=MINIO_BUCKET, Key=key)["Body"].read()
    return key.split("/")[-1], json.loads(body)


def _file_captured_at(path: Path) -> str:
    stamp = path.stem.split("_")[-1]
    parsed = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def load_indodax(cursor) -> dict:
    pairs_name, pairs = _load_latest_bronze("pairs")
    pairs_path = Path(pairs_name)
    pair_rows = [
        (
            item.get("id"),
            item.get("ticker_id"),
            item.get("traded_currency_unit"),
            (item.get("base_currency") or "").upper(),
            (item.get("traded_currency") or "").upper(),
            None,
            None,
            None,
            None,
            _file_captured_at(pairs_path),
            pairs_path.stem,
        )
        for item in pairs
    ]
    pairs_table = _table("pairs")
    _replace_table(cursor, pairs_table, PAIRS_DDL)
    _insert(
        cursor,
        pairs_table,
        ["pair", "ticker_id", "name", "base_currency", "quote_currency",
         "price_decimal_places", "min_price", "max_price", "min_volume",
         "created_at", "run_id"],
        pair_rows,
    )
    logger.info("bronze.pairs: %d rows from %s", len(pair_rows), pairs_path.name)
    ticker_to_pair = {i.get("ticker_id"): i.get("id") for i in pairs}

    summaries_name, summaries = _load_latest_bronze("summaries")
    summaries_path = Path(summaries_name)
    summary_rows = []
    for ticker_key, ticker in summaries.get("tickers", {}).items():
        volume_asset = next(
            (v for k, v in ticker.items() if k.startswith("vol_") and k != "vol_idr"),
            None,
        )
        server_time = ticker.get("server_time")
        created = (
            datetime.fromtimestamp(int(server_time), tz=timezone.utc).isoformat()
            if server_time
            else None
        )
        summary_rows.append(
            (
                ticker_to_pair.get(ticker_key, ticker_key),
                ticker.get("last"),
                ticker.get("buy"),
                ticker.get("sell"),
                ticker.get("high"),
                ticker.get("low"),
                volume_asset,
                ticker.get("vol_idr"),
                created,
                summaries_path.stem,
            )
        )
    summaries_table = _table("summaries")
    _replace_table(cursor, summaries_table, SUMMARIES_DDL)
    _insert(
        cursor,
        summaries_table,
        ["pair", "last", "buy", "sell", "high", "low", "vol_coin",
         "vol_idr", "created_at", "run_id"],
        summary_rows,
    )
    logger.info("bronze.summaries: %d rows from %s", len(summary_rows), summaries_path.name)
    return {"pairs": len(pair_rows), "summaries": len(summary_rows)}


def run_bronze_load() -> dict:
    """Load all Bronze sources into Databricks; returns per-table row counts."""
    from databricks import sql

    server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")
    token = os.getenv("DATABRICKS_TOKEN")
    if not server_hostname or not http_path or not token:
        raise SystemExit(
            "DATABRICKS_SERVER_HOSTNAME / DATABRICKS_HTTP_PATH / "
            "DATABRICKS_TOKEN must be set (see .env)"
        )
    connection = sql.connect(
        server_hostname=server_hostname,
        http_path=http_path,
        access_token=token,
    )
    counts = {}
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS {}.bronze".format(CATALOG))
            counts.update(load_postgres(cursor))
            counts.update(load_mongo(cursor))
            counts.update(load_indodax(cursor))
        finally:
            cursor.close()
    finally:
        connection.close()
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    counts = run_bronze_load()
    print("bronze load complete:", counts)


if __name__ == "__main__":
    main()