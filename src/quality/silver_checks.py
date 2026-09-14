import pandas as pd


class DataQualityError(Exception):
    """Raised when a data quality check fails."""


def validate_market_snapshot(
    dataframe: pd.DataFrame,
) -> None:
    """
    Validate Silver market snapshot data.

    Raises:
        DataQualityError: If one or more quality checks fail.
    """

    errors = []

    # ---------------------------------
    # 1. REQUIRED COLUMNS
    # ---------------------------------

    required_columns = [
        "pair_id",
        "ticker_id",
        "last_price",
        "captured_at",
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

    # Stop here because later checks
    # depend on these columns existing.
    if errors:
        raise DataQualityError(
            "\n".join(errors)
        )

    # ---------------------------------
    # 2. NOT NULL
    # ---------------------------------

    not_null_columns = [
        "pair_id",
        "ticker_id",
        "last_price",
        "captured_at",
    ]

    for column in not_null_columns:
        null_count = dataframe[column].isna().sum()

        if null_count > 0:
            errors.append(
                f"{column} contains {null_count} null values"
            )

    # ---------------------------------
    # 3. UNIQUENESS
    # ---------------------------------

    duplicate_count = dataframe.duplicated(
        subset=[
            "pair_id",
            "captured_at",
        ]
    ).sum()

    if duplicate_count > 0:
        errors.append(
            "Found "
            f"{duplicate_count} duplicate "
            "pair_id + captured_at records"
        )

    # ---------------------------------
    # 4. PRICE VALIDITY
    # ---------------------------------

    invalid_last_price = (
        dataframe["last_price"] <= 0
    ).sum()

    if invalid_last_price > 0:
        errors.append(
            f"Found {invalid_last_price} "
            "records with last_price <= 0"
        )

    # ---------------------------------
    # 5. HIGH >= LOW
    # ---------------------------------

    comparable_prices = dataframe[
        dataframe["high_price"].notna()
        & dataframe["low_price"].notna()
    ]

    invalid_high_low = (
        comparable_prices["high_price"]
        < comparable_prices["low_price"]
    ).sum()

    if invalid_high_low > 0:
        errors.append(
            f"Found {invalid_high_low} records "
            "where high_price < low_price"
        )

    # ---------------------------------
    # 6. VOLUME
    # ---------------------------------

    invalid_volume = (
        dataframe["volume_idr"] < 0
    ).sum()

    if invalid_volume > 0:
        errors.append(
            f"Found {invalid_volume} records "
            "with negative volume_idr"
        )

    # ---------------------------------
    # FINAL RESULT
    # ---------------------------------

    if errors:
        raise DataQualityError(
            "Silver data quality validation failed:\n"
            + "\n".join(
                f"- {error}"
                for error in errors
            )
        )

    print(
        "Silver data quality validation passed."
    )