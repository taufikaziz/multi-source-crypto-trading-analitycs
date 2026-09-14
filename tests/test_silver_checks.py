from datetime import datetime, timezone

import pandas as pd
import pytest

from src.quality.silver_checks import (
    DataQualityError,
    validate_market_snapshot,
)


def create_valid_dataframe():
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
            "last_price": [
                1000000000,
                50000000,
            ],
            "high_price": [
                1100000000,
                55000000,
            ],
            "low_price": [
                900000000,
                45000000,
            ],
            "volume_idr": [
                100000000,
                50000000,
            ],
            "captured_at": [
                datetime(2026, 8, 24, tzinfo=timezone.utc),
                datetime(2026, 8, 24, tzinfo=timezone.utc),
            ],
            "run_id": [
                "20260826T040308Z",
                "20260826T040308Z",
            ],
        }
    )


def test_valid_market_snapshot_passes():
    dataframe = create_valid_dataframe()

    validate_market_snapshot(dataframe)


def test_negative_last_price_fails():
    dataframe = create_valid_dataframe()

    dataframe.loc[0, "last_price"] = -100

    with pytest.raises(DataQualityError):
        validate_market_snapshot(dataframe)


def test_duplicate_pair_snapshot_fails():
    dataframe = create_valid_dataframe()

    dataframe.loc[1, "pair_id"] = "btcidr"

    with pytest.raises(DataQualityError):
        validate_market_snapshot(dataframe)


def test_high_lower_than_low_fails():
    dataframe = create_valid_dataframe()

    dataframe.loc[0, "high_price"] = 100
    dataframe.loc[0, "low_price"] = 200

    with pytest.raises(DataQualityError):
        validate_market_snapshot(dataframe)


def test_negative_volume_fails():
    dataframe = create_valid_dataframe()

    dataframe.loc[0, "volume_idr"] = -1

    with pytest.raises(DataQualityError):
        validate_market_snapshot(dataframe)