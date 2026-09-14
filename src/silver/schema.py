from dataclasses import dataclass


@dataclass(frozen=True)
class SilverMarketSnapshotSchema:
    pair_id: str = "pair_id"
    ticker_id: str = "ticker_id"
    asset_name: str = "asset_name"

    buy_price: str = "buy_price"
    sell_price: str = "sell_price"
    high_price: str = "high_price"
    low_price: str = "low_price"
    last_price: str = "last_price"

    price_24h_ago: str = "price_24h_ago"
    price_7d_ago: str = "price_7d_ago"

    volume_asset: str = "volume_asset"
    volume_idr: str = "volume_idr"

    source_timestamp: str = "source_timestamp"
    captured_at: str = "captured_at"
    ingestion_date: str = "ingestion_date"
    source_file: str = "source_file"


SILVER_MARKET_SNAPSHOT_SCHEMA = SilverMarketSnapshotSchema()