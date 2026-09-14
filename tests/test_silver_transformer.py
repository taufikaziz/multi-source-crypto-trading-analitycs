from datetime import datetime, timezone

from src.silver.transformer import build_market_snapshot


def test_transformer_maps_ticker_to_pair_id():
    pairs = [
        {
            "id": "btcidr",
            "ticker_id": "btc_idr",
        }
    ]

    summaries = {
        "tickers": {
            "btc_idr": {
                "buy": "100",
                "sell": "101",
                "high": "110",
                "low": "90",
                "last": "105",
                "name": "Bitcoin",
                "server_time": 1787552199,
                "vol_btc": "20.5",
                "vol_idr": "2000000000",
            }
        },
        "prices_24h": {
            "btcidr": 95,
        },
        "prices_7d": {
            "btcidr": 80,
        },
    }

    captured_at = datetime(
        2026,
        8,
        24,
        tzinfo=timezone.utc,
    )

    run_id = "20260824T000000Z"

    result = build_market_snapshot(
        pairs=pairs,
        summaries=summaries,
        captured_at=captured_at,
        run_id=run_id,
        source_file="test.json",
    )

    assert len(result) == 1

    row = result.iloc[0]

    assert row["pair_id"] == "btcidr"
    assert row["ticker_id"] == "btc_idr"
    assert row["asset_name"] == "Bitcoin"


def test_transformer_normalizes_dynamic_volume_column():
    pairs = [
        {
            "id": "ethidr",
            "ticker_id": "eth_idr",
        }
    ]

    summaries = {
        "tickers": {
            "eth_idr": {
                "buy": "50000000",
                "sell": "50010000",
                "high": "51000000",
                "low": "49000000",
                "last": "50000000",
                "name": "Ethereum",
                "server_time": 1787552199,
                "vol_eth": "100.25",
                "vol_idr": "5000000000",
            }
        },
        "prices_24h": {
            "ethidr": 49000000,
        },
        "prices_7d": {
            "ethidr": 48000000,
        },
    }

    captured_at = datetime(
        2026,
        8,
        24,
        tzinfo=timezone.utc,
    )

    run_id = "20260824T000000Z"

    result = build_market_snapshot(
        pairs=pairs,
        summaries=summaries,
        captured_at=captured_at,
        run_id=run_id,
        source_file="test.json",
    )

    assert result.iloc[0]["volume_asset"] == 100.25
    assert result.iloc[0]["volume_idr"] == 5000000000