import numpy as np
import pandas as pd


class GoldDataQualityError(Exception):
    """Raised when a Gold data quality check fails."""


def validate_market_metrics(
    dataframe: pd.DataFrame,
) -> None:
    """
    Validate Gold-layer market metrics.

    Raises:
        GoldDataQualityError: If one or more quality checks fail.
    """

    errors = []

    # ---------------------------------
    # 1. REQUIRED COLUMNS
    # ---------------------------------

    required_columns = [
        "pair_id",
        "captured_at",
        "last_price",
        "price_change_24h",
        "price_change_24h_pct",
        "price_change_7d",
        "price_change_7d_pct",
        "spread",
        "spread_pct",
        "volume_rank",
        "run_id",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        errors.append(
            f"Missing required columns: {missing_columns}"
        )

    # Stop because later checks depend
    # on these columns.
    if errors:
        raise GoldDataQualityError(
            "\n".join(errors)
        )

    # ---------------------------------
    # 2. REQUIRED VALUES MUST NOT BE NULL
    # ---------------------------------

    not_null_columns = [
        "pair_id",
        "captured_at",
        "last_price",
    ]

    for column in not_null_columns:
        null_count = dataframe[column].isna().sum()

        if null_count > 0:
            errors.append(
                f"{column} contains {null_count} null values"
            )

    # ---------------------------------
    # 3. UNIQUE SNAPSHOT RECORD
    # ---------------------------------

    duplicate_count = dataframe.duplicated(
        subset=[
            "pair_id",
            "captured_at",
        ]
    ).sum()

    if duplicate_count > 0:
        errors.append(
            f"Found {duplicate_count} duplicate "
            "pair_id + captured_at records"
        )

    # ---------------------------------
    # 4. LAST PRICE MUST BE POSITIVE
    # ---------------------------------

    invalid_last_price = (
        dataframe["last_price"] <= 0
    ).sum()

    if invalid_last_price > 0:
        errors.append(
            f"Found {invalid_last_price} records "
            "with last_price <= 0"
        )

    # ---------------------------------
    # 5. VOLUME RANK MUST START FROM 1
    # ---------------------------------

    invalid_volume_rank = (
        dataframe["volume_rank"].notna()
        & (dataframe["volume_rank"] < 1)
    ).sum()

    if invalid_volume_rank > 0:
        errors.append(
            f"Found {invalid_volume_rank} records "
            "with volume_rank < 1"
        )

    # ---------------------------------
    # 6. SPREAD CALCULATION CONSISTENCY
    # ---------------------------------

    expected_spread = (
        dataframe["sell_price"]
        - dataframe["buy_price"]
    )

    invalid_spread = ~np.isclose(
        dataframe["spread"],
        expected_spread,
        equal_nan=True,
    )

    invalid_spread_count = invalid_spread.sum()

    if invalid_spread_count > 0:
        errors.append(
            f"Found {invalid_spread_count} records "
            "with inconsistent spread calculation"
        )

    # ---------------------------------
    # 7. 24H PRICE CHANGE CONSISTENCY
    # ---------------------------------

    expected_change_24h = (
        dataframe["last_price"]
        - dataframe["price_24h_ago"]
    )

    invalid_change_24h = ~np.isclose(
        dataframe["price_change_24h"],
        expected_change_24h,
        equal_nan=True,
    )

    invalid_change_24h_count = (
        invalid_change_24h.sum()
    )

    if invalid_change_24h_count > 0:
        errors.append(
            f"Found {invalid_change_24h_count} records "
            "with inconsistent 24h price change"
        )

    # ---------------------------------
    # 8. 7D PRICE CHANGE CONSISTENCY
    # ---------------------------------

    expected_change_7d = (
        dataframe["last_price"]
        - dataframe["price_7d_ago"]
    )

    invalid_change_7d = ~np.isclose(
        dataframe["price_change_7d"],
        expected_change_7d,
        equal_nan=True,
    )

    invalid_change_7d_count = (
        invalid_change_7d.sum()
    )

    if invalid_change_7d_count > 0:
        errors.append(
            f"Found {invalid_change_7d_count} records "
            "with inconsistent 7d price change"
        )

    # ---------------------------------
    # FINAL RESULT
    # ---------------------------------

    if errors:
        raise GoldDataQualityError(
            "Gold data quality validation failed:\n"
            + "\n".join(
                f"- {error}"
                for error in errors
            )
        )

    print(
        "Gold data quality validation passed."
    )