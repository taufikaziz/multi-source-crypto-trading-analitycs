from src.warehouse.connection import get_connection


def create_warehouse_schema() -> None:
    """
    Create the Data Warehouse tables if they do not exist.
    """

    connection = get_connection()

    try:
        # ---------------------------------
        # DIMENSION: MARKET
        # ---------------------------------

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS dim_market (
                market_key BIGINT PRIMARY KEY,
                pair_id VARCHAR NOT NULL UNIQUE,
                ticker_id VARCHAR NOT NULL,
                asset_name VARCHAR
            )
            """
        )

        # ---------------------------------
        # DIMENSION: DATE
        # ---------------------------------

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS dim_date (
                date_key INTEGER PRIMARY KEY,
                full_date DATE NOT NULL UNIQUE,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL
            )
            """
        )

        # ---------------------------------
        # FACT: MARKET SNAPSHOT
        # ---------------------------------

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fact_market_snapshot (
                market_key BIGINT NOT NULL,
                date_key INTEGER NOT NULL,
                captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
                run_id VARCHAR NOT NULL,

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
                volume_rank BIGINT,

                PRIMARY KEY (
                    market_key,
                    captured_at
                ),

                FOREIGN KEY (market_key)
                    REFERENCES dim_market(market_key),

                FOREIGN KEY (date_key)
                    REFERENCES dim_date(date_key)
            )
            """
        )

    finally:
        connection.close()