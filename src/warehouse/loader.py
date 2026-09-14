from datetime import datetime

import pandas as pd

from src.warehouse.connection import get_connection


class WarehouseLoader:
    """
    Load Gold layer data into the DuckDB Data Warehouse.
    """

    def __init__(
        self,
        connection=None,
    ):
        self.connection = connection
        
    def load_market_snapshot(
        self,
        dataframe: pd.DataFrame,
    ) -> None:

        connection = (
            self.connection
            if self.connection is not None
            else get_connection()
        )

        should_close_connection = (
            self.connection is None
        )

        try:
            self._load_dim_market(
                connection=connection,
                dataframe=dataframe,
            )

            self._load_dim_date(
                connection=connection,
                dataframe=dataframe,
            )

            self._load_fact_market_snapshot(
                connection=connection,
                dataframe=dataframe,
            )

        finally:
            if should_close_connection:
                connection.close()

    def _load_dim_market(
        self,
        connection,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Load unique market records into dim_market.
        """

        markets_df = (
            dataframe[
                [
                    "pair_id",
                    "ticker_id",
                    "asset_name",
                ]
            ]
            .drop_duplicates(
                subset=["pair_id"]
            )
            .copy()
        )

        connection.register(
            "markets_df",
            markets_df,
        )

        connection.execute(
            """
            INSERT INTO dim_market (
                market_key,
                pair_id,
                ticker_id,
                asset_name
            )
            SELECT
                COALESCE(
                    (
                        SELECT MAX(market_key)
                        FROM dim_market
                    ),
                    0
                )
                + ROW_NUMBER() OVER (
                    ORDER BY pair_id
                ) AS market_key,
                pair_id,
                ticker_id,
                asset_name
            FROM markets_df
            WHERE pair_id NOT IN (
                SELECT pair_id
                FROM dim_market
            )
            """
        )

        connection.unregister(
            "markets_df"
        )

    def _load_dim_date(
        self,
        connection,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Load unique dates into dim_date.
        """

        dates_df = pd.DataFrame(
            {
                "full_date": pd.to_datetime(
                    dataframe["captured_at"]
                )
                .dt.date
                .drop_duplicates()
            }
        )

        dates_df["date_key"] = (
            pd.to_datetime(
                dates_df["full_date"]
            )
            .dt.strftime("%Y%m%d")
            .astype(int)
        )

        dates_df["year"] = pd.to_datetime(
            dates_df["full_date"]
        ).dt.year

        dates_df["month"] = pd.to_datetime(
            dates_df["full_date"]
        ).dt.month

        dates_df["day"] = pd.to_datetime(
            dates_df["full_date"]
        ).dt.day

        connection.register(
            "dates_df",
            dates_df,
        )

        connection.execute(
            """
            INSERT INTO dim_date (
                date_key,
                full_date,
                year,
                month,
                day
            )
            SELECT
                date_key,
                full_date,
                year,
                month,
                day
            FROM dates_df
            WHERE date_key NOT IN (
                SELECT date_key
                FROM dim_date
            )
            """
        )

        connection.unregister(
            "dates_df"
        )

    def _load_fact_market_snapshot(
        self,
        connection,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Load Gold market metrics into fact table.
        """

        connection.register(
            "gold_df",
            dataframe,
        )

        connection.execute(
            """
            INSERT INTO fact_market_snapshot (
                market_key,
                date_key,
                captured_at,
                run_id,
                buy_price,
                sell_price,
                high_price,
                low_price,
                last_price,
                price_change_24h_pct,
                price_change_7d_pct,
                spread_pct,
                volume_asset,
                volume_idr,
                volume_rank
            )
            SELECT
                market.market_key,

                CAST(
                    STRFTIME(
                        gold.captured_at,
                        '%Y%m%d'
                    ) AS INTEGER
                ) AS date_key,

                gold.captured_at,
                gold.run_id,

                gold.buy_price,
                gold.sell_price,
                gold.high_price,
                gold.low_price,
                gold.last_price,

                gold.price_change_24h_pct,
                gold.price_change_7d_pct,
                gold.spread_pct,

                gold.volume_asset,
                gold.volume_idr,
                gold.volume_rank

            FROM gold_df AS gold

            INNER JOIN dim_market AS market
                ON gold.pair_id = market.pair_id

            WHERE NOT EXISTS (
                SELECT 1
                FROM fact_market_snapshot AS fact
                WHERE fact.market_key = market.market_key
                  AND fact.captured_at = gold.captured_at
            )
            """
        )

        connection.unregister(
            "gold_df"
        )