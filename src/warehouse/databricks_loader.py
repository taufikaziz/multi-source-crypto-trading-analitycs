import os
import logging

import pandas as pd
from databricks import sql
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def _to_int_or_none(value):
    if pd.isna(value):
        return None
    return int(value)


def _to_float_or_none(value):
    if pd.isna(value):
        return None
    return float(value)

class DatabricksWarehouseLoader:
    """
    Load Gold layer data into Databricks.
    """

    def __init__(self):
        self.server_hostname = os.getenv(
            "DATABRICKS_SERVER_HOSTNAME"
        )

        self.http_path = os.getenv(
            "DATABRICKS_HTTP_PATH"
        )

    def _get_connection(self):
        print("Connecting to Databricks...")

        token = os.getenv("DATABRICKS_TOKEN")
        if token:
            connection = sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                auth_type="access-token",
                access_token=token,
            )
        else:
            connection = sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                auth_type="databricks-oauth",
            )

        print("Databricks connection established.")

        return connection

    def load_market_snapshot(
        self,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Load market snapshot into Databricks.
        """

        print(
            f"Starting Databricks warehouse load: "
            f"{len(dataframe)} rows"
        )

        connection = self._get_connection()

        print("Connection object created.")

        try:
            print("Creating cursor...")

            cursor = connection.cursor()

            print("Cursor created.")

            try:
                print("Loading dim_market...")

                self._load_dim_market(
                    cursor=cursor,
                    dataframe=dataframe,
                )

                print("dim_market completed.")

                print("Loading dim_date...")

                self._load_dim_date(
                    cursor=cursor,
                    dataframe=dataframe,
                )

                print("dim_date completed.")

                print("Loading fact_market_snapshot...")

                self._load_fact_market_snapshot(
                    cursor=cursor,
                    dataframe=dataframe,
                )

                print(
                    "fact_market_snapshot completed."
                )

            finally:
                cursor.close()

        finally:
            connection.close()

        print(
            "Databricks warehouse load completed successfully."
        )

    def _load_dim_market(
        self,
        cursor,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Load new market records into dim_market.
        """

        print("Checking existing dim_market records...")

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

        # Get existing pair_ids
        cursor.execute(
            """
            SELECT pair_id
            FROM workspace.indodax_market_data.dim_market
            """
        )

        existing_pair_ids = {
            row[0]
            for row in cursor.fetchall()
        }

        # Keep only new markets
        new_markets_df = markets_df[
            ~markets_df["pair_id"].isin(
                existing_pair_ids
            )
        ]

        print(
            f"New dim_market rows: "
            f"{len(new_markets_df)}"
        )

        # Nothing new to insert
        if new_markets_df.empty:
            print(
                "No new dim_market records."
            )
            return

        rows = list(
            new_markets_df.itertuples(
                index=False,
                name=None,
            )
        )

        print(
            f"Inserting {len(rows)} "
            "new dim_market records..."
        )

        cursor.executemany(
            """
            INSERT INTO
            workspace.indodax_market_data.dim_market (
                pair_id,
                ticker_id,
                asset_name
            )
            VALUES (?, ?, ?)
            """,
            rows,
        )

        print(
            "dim_market insert completed."
        )

    def _load_dim_date(
        self,
        cursor,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Load new dates into dim_date.
        """

        dates_df = pd.DataFrame(
            {
                "full_date": (
                    pd.to_datetime(
                        dataframe["captured_at"],
                        utc=True,
                    )
                    .dt.date
                    .drop_duplicates()
                )
            }
        )

        dates_df["date_key"] = (
            pd.to_datetime(
                dates_df["full_date"]
            )
            .dt.strftime("%Y%m%d")
            .astype(int)
        )

        dates_df["year"] = (
            pd.to_datetime(
                dates_df["full_date"]
            )
            .dt.year
        )

        dates_df["month"] = (
            pd.to_datetime(
                dates_df["full_date"]
            )
            .dt.month
        )

        dates_df["day"] = (
            pd.to_datetime(
                dates_df["full_date"]
            )
            .dt.day
        )

        print(
            "Checking existing dim_date records..."
        )

        cursor.execute(
            """
            SELECT date_key
            FROM workspace.indodax_market_data.dim_date
            """
        )

        existing_date_keys = {
            row[0]
            for row in cursor.fetchall()
        }

        new_dates_df = dates_df[
            ~dates_df["date_key"].isin(
                existing_date_keys
            )
        ]

        print(
            f"New dim_date rows: "
            f"{len(new_dates_df)}"
        )

        if new_dates_df.empty:
            print(
                "No new dim_date records."
            )
            return

        rows = list(
            new_dates_df[
                [
                    "date_key",
                    "full_date",
                    "year",
                    "month",
                    "day",
                ]
            ].itertuples(
                index=False,
                name=None,
            )
        )

        cursor.executemany(
            """
            INSERT INTO
            workspace.indodax_market_data.dim_date (
                date_key,
                full_date,
                year,
                month,
                day
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

        print(
            "dim_date insert completed."
        )
    def _load_fact_market_snapshot(
        self,
        cursor,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Load Gold market metrics into fact_market_snapshot.
        """

        # =========================
        # GET MARKET KEYS
        # =========================

        cursor.execute(
            """
            SELECT
                market_key,
                pair_id
            FROM workspace.indodax_market_data.dim_market
            """
        )

        market_rows = cursor.fetchall()

        market_mapping = {
            row[1]: row[0]
            for row in market_rows
        }

        # =========================
        # PREPARE FACT DATA
        # =========================

        fact_df = dataframe.copy()

        fact_df["market_key"] = (
            fact_df["pair_id"].map(
                market_mapping
            )
        )

        missing_market_keys = fact_df[
            fact_df["market_key"].isna()
        ]

        if not missing_market_keys.empty:
            missing_pairs = (
                missing_market_keys["pair_id"]
                .unique()
                .tolist()
            )

            raise ValueError(
                "Market key not found for pair_id: "
                f"{missing_pairs}"
            )

        fact_df["market_key"] = (
            fact_df["market_key"].astype(int)
        )

        fact_df["date_key"] = (
            pd.to_datetime(
                fact_df["captured_at"],
                utc=True,
            )
            .dt.strftime("%Y%m%d")
            .astype(int)
        )

        # =========================
        # CHECK EXISTING SNAPSHOTS
        # =========================

        cursor.execute(
            """
            SELECT
                market_key,
                captured_at
            FROM workspace.indodax_market_data.fact_market_snapshot
            """
        )
        print("Existing fact query completed.")

        existing_rows = cursor.fetchall()
        print(
            f"Existing fact rows: {len(existing_rows)}"
        )
        
        existing_snapshots = {
            (
                row[0],
                row[1],
            )
            for row in existing_rows
        }

        # =========================
        # BUILD NEW ROWS ONLY
        # =========================

        rows_to_insert = []

        for row in fact_df.itertuples(
            index=False,
        ):

            snapshot_key = (
                row.market_key,
                row.captured_at,
            )

            if snapshot_key in existing_snapshots:
                continue

            rows_to_insert.append(
                (
                    int(row.market_key),
                    int(row.date_key),
                    row.captured_at.to_pydatetime()
                    if hasattr(row.captured_at, "to_pydatetime")
                    else row.captured_at,
                    str(row.run_id),
                    float(row.buy_price),
                    float(row.sell_price),
                    float(row.high_price),
                    float(row.low_price),
                    float(row.last_price),
                    float(row.price_change_24h_pct),
                    float(row.price_change_7d_pct),
                    float(row.spread_pct),
                    float(row.volume_asset),
                    float(row.volume_idr),
                    _to_int_or_none(
                        row.volume_rank,
                ),
                )
            ),

        # =========================
        # INSERT FACT DATA
        # =========================
        logger.info(
            "Fact rows prepared for insert: %s",
            len(rows_to_insert),
        )
        if not rows_to_insert:
            return

        cursor.executemany(
            """
            INSERT INTO
            workspace.indodax_market_data.fact_market_snapshot (
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
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?
            )
            """,
            rows_to_insert,
        )
        logger.info(
            "Fact rows inserted successfully: %s",
            len(rows_to_insert),
        )