"""Load Bronze tables into the DuckDB dev warehouse.

Reads the three source systems in their raw form and materializes
queryable bronze.* tables consumed by dbt staging models
(dbt_crypto_platform/models/staging/*). Indodax JSON files are reshaped
into the tabular bronze contract (see docs/bronze_contract.md);
PostgreSQL tables are copied as-is; MongoDB documents keep their raw
envelope with context stored as a JSON string.

Usage (from repo root, postgres port published on 127.0.0.1:5432):
    .venv/Scripts/python.exe scripts/load_bronze_duckdb.py
"""

import glob
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb

WAREHOUSE_PATH = os.getenv(
    "DBT_DUCKDB_PATH", "data/warehouse/indodax.duckdb"
)
PG_DSN = os.getenv(
    "POSTGRES_APP_DSN",
    "postgresql://airflow:Airflowxyz@127.0.0.1:5432/indodax",
)
MONGO_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://mongodb:Mongodbxyz@127.0.0.1:27017/indodax?authSource=admin",
)
MONGO_DB = os.getenv("MONGO_DATABASE", "indodax")
BRONZE_BASE = Path(os.getenv("BRONZE_BASE_PATH", "data/bronze"))

PG_TABLES = {
    "users": (
        "user_id TEXT, email TEXT, full_name TEXT, "
        "is_active BOOLEAN, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ"
    ),
    "accounts": (
        "account_id TEXT, user_id TEXT, currency TEXT, "
        "balance DECIMAL(18,8), locked_balance DECIMAL(18,8), "
        "created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ"
    ),
    "assets": "asset_id TEXT, symbol TEXT, name TEXT, precision INTEGER, created_at TIMESTAMPTZ",
    "orders": (
        "order_id TEXT, user_id TEXT, pair TEXT, order_type TEXT, "
        "price DECIMAL(18,8), quantity DECIMAL(18,8), "
        "filled_quantity DECIMAL(18,8), status TEXT, "
        "created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ"
    ),
    "trades": (
        "trade_id TEXT, order_id TEXT, price DECIMAL(18,8), "
        "quantity DECIMAL(18,8), taker_side TEXT, executed_at TIMESTAMPTZ"
    ),
    "transactions": (
        "transaction_id TEXT, account_id TEXT, amount DECIMAL(18,8), "
        "type TEXT, status TEXT, created_at TIMESTAMPTZ"
    ),
}


def latest_file(dataset: str) -> Path:
    files = sorted(
        glob.glob(str(BRONZE_BASE / "source=indodax" / f"dataset={dataset}" / "**" / "*.json"), recursive=True)
    )
    if not files:
        raise SystemExit(f"no bronze files for dataset={dataset}")
    return Path(files[-1])


def file_run_id(path: Path) -> str:
    return path.stem


def file_captured_at(path: Path) -> str:
    stamp = path.stem.split("_")[-1]
    parsed = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def load_postgres(connection) -> None:
    import psycopg2

    pg_conn = psycopg2.connect(PG_DSN)
    try:
        cursor = pg_conn.cursor()
        for table, ddl in PG_TABLES.items():
            cursor.execute(f"SELECT * FROM {table}")
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
            connection.execute(
                f"CREATE OR REPLACE TABLE bronze.{table} ({ddl})"
            )
            connection.executemany(
                f"INSERT INTO bronze.{table} ({', '.join(columns)}) "
                f"VALUES ({', '.join(['?'] * len(columns))})",
                rows,
            )
            print(f"bronze.{table}: {len(rows)} rows from postgres")
    finally:
        pg_conn.close()


def load_mongo(connection) -> None:
    from pymongo import MongoClient

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=15000)
    try:
        docs = list(client[MONGO_DB].user_events.find())
    finally:
        client.close()
    rows = [
        (
            str(doc["_id"]),
            doc.get("event"),
            json.dumps(doc.get("context", {}), ensure_ascii=False),
            doc.get("ingested_at"),
        )
        for doc in docs
    ]
    connection.execute(
        "CREATE OR REPLACE TABLE bronze.user_events "
        "(_id TEXT, event TEXT, context VARCHAR, ingested_at TEXT)"
    )
    connection.executemany(
        "INSERT INTO bronze.user_events (_id, event, context, ingested_at) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )
    print(f"bronze.user_events: {len(rows)} docs from mongodb")


def load_indodax(connection) -> None:
    pairs_path = latest_file("pairs")
    pairs = json.loads(pairs_path.read_text(encoding="utf-8"))
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
            file_captured_at(pairs_path),
            file_run_id(pairs_path),
        )
        for item in pairs
    ]
    connection.execute(
        "CREATE OR REPLACE TABLE bronze.pairs (pair TEXT, ticker_id TEXT, "
        "name TEXT, base_currency TEXT, quote_currency TEXT, "
        "price_decimal_places INTEGER, min_price DECIMAL(18,8), "
        "max_price DECIMAL(18,8), min_volume DECIMAL(18,8), "
        "created_at TIMESTAMPTZ, run_id TEXT)"
    )
    connection.executemany(
        "INSERT INTO bronze.pairs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        pair_rows,
    )
    print(f"bronze.pairs: {len(pair_rows)} rows from {pairs_path.name}")
    ticker_to_pair = {i.get("ticker_id"): i.get("id") for i in pairs}

    summaries_path = latest_file("summaries")
    summaries = json.loads(summaries_path.read_text(encoding="utf-8"))
    summary_rows = []
    for ticker_key, ticker in summaries.get("tickers", {}).items():
        volume_asset = next(
            (v for k, v in ticker.items()
             if k.startswith("vol_") and k != "vol_idr"),
            None,
        )
        server_time = ticker.get("server_time")
        created = (
            datetime.fromtimestamp(int(server_time), tz=timezone.utc).isoformat()
            if server_time else None
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
                file_run_id(summaries_path),
            )
        )
    connection.execute(
        "CREATE OR REPLACE TABLE bronze.summaries (pair TEXT, last TEXT, "
        "buy TEXT, sell TEXT, high TEXT, low TEXT, vol_coin TEXT, "
        "vol_idr TEXT, created_at TIMESTAMPTZ, run_id TEXT)"
    )
    connection.executemany(
        "INSERT INTO bronze.summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        summary_rows,
    )
    print(f"bronze.summaries: {len(summary_rows)} rows from {summaries_path.name}")


def main() -> None:
    connection = duckdb.connect(WAREHOUSE_PATH)
    try:
        connection.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        load_postgres(connection)
        load_mongo(connection)
        load_indodax(connection)
        tables = connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'bronze' ORDER BY 1"
        ).fetchall()
        print("bronze tables:", [t[0] for t in tables])
    finally:
        connection.close()


if __name__ == "__main__":
    main()