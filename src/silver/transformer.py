import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _volume_asset(ticker: Dict[str, Any]) -> float:
    for key, value in ticker.items():
        if key.startswith("vol_") and key != "vol_idr":
            return _to_float(value)
    return math.nan


def _source_timestamp(ticker: Dict[str, Any]) -> Optional[datetime]:
    server_time = ticker.get("server_time")
    try:
        return datetime.fromtimestamp(int(server_time), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def build_market_snapshot(
    pairs: List[Dict[str, Any]],
    summaries: Dict[str, Any],
    captured_at: datetime,
    source_file: str,
    run_id: str,
) -> pd.DataFrame:
    tickers = summaries.get("tickers", {})
    prices_24h = summaries.get("prices_24h", {})
    prices_7d = summaries.get("prices_7d", {})

    rows = []
    for pair in pairs:
        pair_id = pair.get("id")
        ticker_id = pair.get("ticker_id")
        ticker = tickers.get(ticker_id)
        if ticker is None:
            continue
        rows.append(
            {
                "pair_id": pair_id,
                "ticker_id": ticker_id,
                "asset_name": ticker.get("name"),
                "buy_price": _to_float(ticker.get("buy")),
                "sell_price": _to_float(ticker.get("sell")),
                "high_price": _to_float(ticker.get("high")),
                "low_price": _to_float(ticker.get("low")),
                "last_price": _to_float(ticker.get("last")),
                "price_24h_ago": _to_float(prices_24h.get(pair_id)),
                "price_7d_ago": _to_float(prices_7d.get(pair_id)),
                "volume_asset": _volume_asset(ticker),
                "volume_idr": _to_float(ticker.get("vol_idr")),
                "source_timestamp": _source_timestamp(ticker),
                "captured_at": captured_at,
                "ingestion_date": captured_at.strftime("%Y-%m-%d"),
                "source_file": source_file,
                "run_id": run_id,
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "pair_id",
            "ticker_id",
            "asset_name",
            "buy_price",
            "sell_price",
            "high_price",
            "low_price",
            "last_price",
            "price_24h_ago",
            "price_7d_ago",
            "volume_asset",
            "volume_idr",
            "source_timestamp",
            "captured_at",
            "ingestion_date",
            "source_file",
            "run_id",
        ],
    )