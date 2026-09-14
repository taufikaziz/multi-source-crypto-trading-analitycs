import pandas as pd
import pytest

from src.gold.transformer import build_market_metrics


def test_build_market_metrics_calculates_price_changes():
    df = pd.DataFrame(
        {
            "pair_id": ["btcidr"],
            "last_price": [110.0],
            "price_24h_ago": [100.0],
            "price_7d_ago": [80.0],
            "buy_price": [108.0],
            "sell_price": [112.0],
            "volume_idr": [1_000_000.0],
        }
    )

    result = build_market_metrics(df)

    row = result.iloc[0]

    assert row["price_change_24h"] == 10.0
    assert row["price_change_24h_pct"] == 10.0

    assert row["price_change_7d"] == 30.0
    assert row["price_change_7d_pct"] == 37.5


def test_build_market_metrics_calculates_spread():
    df = pd.DataFrame(
        {
            "pair_id": ["btcidr"],
            "last_price": [110.0],
            "price_24h_ago": [100.0],
            "price_7d_ago": [80.0],
            "buy_price": [100.0],
            "sell_price": [105.0],
            "volume_idr": [1_000_000.0],
        }
    )

    result = build_market_metrics(df)

    row = result.iloc[0]

    assert row["spread"] == 5.0
    assert row["spread_pct"] == 5.0


def test_build_market_metrics_ranks_volume():
    df = pd.DataFrame(
        {
            "pair_id": ["a", "b", "c"],
            "last_price": [100.0, 100.0, 100.0],
            "price_24h_ago": [90.0, 90.0, 90.0],
            "price_7d_ago": [80.0, 80.0, 80.0],
            "buy_price": [99.0, 99.0, 99.0],
            "sell_price": [101.0, 101.0, 101.0],
            "volume_idr": [
                3_000_000.0,
                2_000_000.0,
                1_000_000.0,
            ],
        }
    )

    result = build_market_metrics(df)

    assert result["volume_rank"].tolist() == [1, 2, 3]


def test_build_market_metrics_allows_missing_volume():
    df = pd.DataFrame(
        {
            "pair_id": ["btcusdt"],
            "last_price": [110.0],
            "price_24h_ago": [100.0],
            "price_7d_ago": [80.0],
            "buy_price": [108.0],
            "sell_price": [112.0],
            "volume_idr": [None],
        }
    )

    result = build_market_metrics(df)

    assert pd.isna(
        result.loc[0, "volume_rank"]
    )