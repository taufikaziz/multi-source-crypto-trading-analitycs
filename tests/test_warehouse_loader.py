from datetime import datetime, timezone

import duckdb
import pandas as pd

from src.warehouse.loader import WarehouseLoader


def create_test_dataframe() -> pd.DataFrame:
    """
    Create a small Gold-like DataFrame
    for warehouse integration testing.
    """

    captured_at = datetime(
        2026,
        8,
        26,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )

    return pd.DataFrame(
        {
            "pair_id": [
                "btcidr",
                "ethidr",
            ],
            "ticker_id": [
                "btc_idr",
                "eth_idr",
            ],
            "asset_name": [
                "Bitcoin",
                "Ethereum",
            ],
            "buy_price": [
                1000000000.0,
                50000000.0,
            ],
            "sell_price": [
                1000100000.0,
                50010000.0,
            ],
            "high_price": [
                1010000000.0,
                51000000.0,
            ],
            "low_price": [
                990000000.0,
                49000000.0,
            ],
            "last_price": [
                1000050000.0,
                50005000.0,
            ],
            "price_change_24h_pct": [
                1.5,
                -0.5,
            ],
            "price_change_7d_pct": [
                5.0,
                2.0,
            ],
            "spread_pct": [
                0.01,
                0.02,
            ],
            "volume_asset": [
                10.0,
                100.0,
            ],
            "volume_idr": [
                10000000000.0,
                5000000000.0,
            ],
            "volume_rank": [
                1,
                2,
            ],
            "captured_at": [
                captured_at,
                captured_at,
            ],
            "run_id": [
                "20260826T120000Z",
                "20260826T120000Z",
            ],
        }
    )


def create_test_tables(connection) -> None:
    """
    Create warehouse tables in an
    in-memory DuckDB database.
    """

    connection.execute(
        """
        CREATE TABLE dim_market (
            market_key BIGINT PRIMARY KEY,
            pair_id VARCHAR UNIQUE,
            ticker_id VARCHAR,
            asset_name VARCHAR
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE dim_date (
            date_key INTEGER PRIMARY KEY,
            full_date DATE,
            year INTEGER,
            month INTEGER,
            day INTEGER
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE fact_market_snapshot (
            market_key BIGINT,
            date_key INTEGER,
            captured_at TIMESTAMPTZ,
            run_id VARCHAR,

            buy_price DOUBLE,
            sell_price DOUBLE,
            high_price DOUBLE,
            low_price DOUBLE,
            last_price DOUBLE,

            price_change_24h_pct DOUBLE,
            price_change_7d_pct DOUBLE,
            spread_pct DOUBLE,

            volume_asset DOUBLE,
            volume_idr DOUBLE,
            volume_rank INTEGER
        )
        """
    )


def test_warehouse_loader_loads_dimensions_and_facts():
    """
    Test that the warehouse loader correctly loads
    dimensions and fact records.
    """

    connection = duckdb.connect(
        ":memory:"
    )

    try:
        create_test_tables(
            connection
        )

        dataframe = create_test_dataframe()

        loader = WarehouseLoader(
            connection=connection
        )

        loader.load_market_snapshot(
            dataframe=dataframe,
        )

        dim_market_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM dim_market
            """
        ).fetchone()[0]

        dim_date_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM dim_date
            """
        ).fetchone()[0]

        fact_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_market_snapshot
            """
        ).fetchone()[0]

        assert dim_market_count == 2
        assert dim_date_count == 1
        assert fact_count == 2

    finally:
        connection.close()