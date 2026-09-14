from src.warehouse.connection import get_connection


def main():
    connection = get_connection()

    try:
        print("\n=== WAREHOUSE ROW COUNTS ===")

        tables = [
            "dim_market",
            "dim_date",
            "fact_market_snapshot",
        ]

        for table_name in tables:
            result = connection.execute(
                f"""
                SELECT COUNT(*) AS row_count
                FROM {table_name}
                """
            ).fetchone()

            print(
                f"{table_name}: {result[0]}"
            )

        print("\n=== DIM MARKET SAMPLE ===")

        dim_market = connection.execute(
            """
            SELECT
                market_key,
                pair_id,
                ticker_id,
                asset_name
            FROM dim_market
            ORDER BY market_key
            LIMIT 10
            """
        ).fetchdf()

        print(dim_market)

        print("\n=== DIM DATE ===")

        dim_date = connection.execute(
            """
            SELECT *
            FROM dim_date
            ORDER BY date_key
            """
        ).fetchdf()

        print(dim_date)

        print("\n=== FACT MARKET SNAPSHOT SAMPLE ===")

        fact = connection.execute(
            """
            SELECT
                fact.market_key,
                market.pair_id,
                fact.date_key,
                fact.captured_at,
                fact.run_id,
                fact.last_price,
                fact.price_change_24h_pct,
                fact.spread_pct,
                fact.volume_rank
            FROM fact_market_snapshot AS fact
            INNER JOIN dim_market AS market
                ON fact.market_key = market.market_key
            ORDER BY
                fact.captured_at DESC,
                fact.market_key
            LIMIT 10
            """
        ).fetchdf()

        print(fact)

    finally:
        connection.close()


if __name__ == "__main__":
    main()