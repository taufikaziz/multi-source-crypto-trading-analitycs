import pandas as pd
import pytest

from src.quality.gold_checks import (
    GoldDataQualityError,
    validate_market_metrics,
)


def create_valid_gold_dataframe() -> pd.DataFrame:
    """
    Create a valid Gold DataFrame for testing.
    """

    return pd.DataFrame(
        {
            "pair_id": ["btcidr"],
            "captured_at": ["2026-08-26T04:00:00Z"],
            "last_price": [110.0],
            "buy_price": [108.0],
            "sell_price": [112.0],
            "price_24h_ago": [100.0],
            "price_7d_ago": [80.0],
            "price_change_24h": [10.0],
            "price_change_24h_pct": [10.0],
            "price_change_7d": [30.0],
            "price_change_7d_pct": [37.5],
            "spread": [4.0],
            "spread_pct": [
                (4.0 / 108.0) * 100
            ],
            "volume_rank": [1],
            "run_id": ["20260826T040308Z"],
        }
    )


def test_valid_market_metrics_passes():
    df = create_valid_gold_dataframe()

    validate_market_metrics(df)


def test_missing_required_column_fails():
    df = create_valid_gold_dataframe()

    df = df.drop(
        columns=["spread"]
    )

    with pytest.raises(
        GoldDataQualityError,
        match="Missing required columns",
    ):
        validate_market_metrics(df)


def test_duplicate_pair_snapshot_fails():
    df = create_valid_gold_dataframe()

    df = pd.concat(
        [df, df],
        ignore_index=True,
    )

    with pytest.raises(
        GoldDataQualityError,
        match="duplicate",
    ):
        validate_market_metrics(df)


def test_zero_last_price_fails():
    df = create_valid_gold_dataframe()

    df.loc[0, "last_price"] = 0.0

    with pytest.raises(
        GoldDataQualityError,
        match="last_price <= 0",
    ):
        validate_market_metrics(df)


def test_negative_volume_rank_fails():
    df = create_valid_gold_dataframe()

    df.loc[0, "volume_rank"] = -1

    with pytest.raises(
        GoldDataQualityError,
        match="volume_rank < 1",
    ):
        validate_market_metrics(df)


def test_inconsistent_spread_fails():
    df = create_valid_gold_dataframe()

    df.loc[0, "spread"] = 999.0

    with pytest.raises(
        GoldDataQualityError,
        match="inconsistent spread calculation",
    ):
        validate_market_metrics(df)


def test_inconsistent_24h_price_change_fails():
    df = create_valid_gold_dataframe()

    df.loc[0, "price_change_24h"] = 999.0

    with pytest.raises(
        GoldDataQualityError,
        match="inconsistent 24h price change",
    ):
        validate_market_metrics(df)


def test_inconsistent_7d_price_change_fails():
    df = create_valid_gold_dataframe()

    df.loc[0, "price_change_7d"] = 999.0

    with pytest.raises(
        GoldDataQualityError,
        match="inconsistent 7d price change",
    ):
        validate_market_metrics(df)


def test_null_volume_rank_is_allowed():
    df = create_valid_gold_dataframe()

    df.loc[0, "volume_rank"] = None

    validate_market_metrics(df)