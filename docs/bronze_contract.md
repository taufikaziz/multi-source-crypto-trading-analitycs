# Bronze Layer Data Contract

## Overview

Bronze layer menyimpan data mentah (raw) dari berbagai source system tanpa transformasi. Data disimpan dalam format file partitioned berdasarkan timestamp ingestion dan source identifier.

---

## Storage Configuration

| Property | Value |
|----------|-------|
| **Base Path** | `s3://indodax-warehouse/bronze/` |
| **File Format** | `parquet` |
| **Partitioning** | `source, DATE(ingested_at), HOUR(ingested_at)` |
| **Compression** | `snappy` |
| **Watermark Table** | PostgreSQL `etl_watermark` (table: `bronze` namespace) |

---

## Bronze Datasets

### 1. PostgreSQL — Orders (`orders`)

| Property | Value |
|----------|-------|
| **Source** | PostgreSQL — `orders` table |
| **Namespace** | `postgres.orders` |
| **File Name** | `orders_ingested_at={ts}_source=postgres.parquet` |
| **Ingestion Trigger** | `updated_at` > last_watermark |
| **Watermark Column** | `updated_at` (TIMESTAMPTZ) |

#### Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | `STRING` | UUID primary key |
| `user_id` | `STRING` | Foreign key ke users |
| `pair` | `STRING` | Trading pair (e.g., `BTCIDR`) |
| `type` | `STRING` | `buy` / `sell` |
| `price` | `DECIMAL(18,8)` | Order price |
| `quantity` | `DECIMAL(18,8)` | Order quantity |
| `status` | `STRING` | `open` / `filled` / `cancelled` |
| `created_at` | `TIMESTAMPTZ` | Original creation time |
| `updated_at` | `TIMESTAMPTZ` | Last update (watermark) |
| `executed_at` | `TIMESTAMPTZ` | Execution time (nullable) |
| `ingested_at` | `TIMESTAMPTZ` | ETL ingestion timestamp (DuckDB-generated) |
| `source` | `STRING` | Source identifier (`postgres`) |

---

### 2. PostgreSQL — Trades (`trades`)

| Property | Value |
|----------|-------|
| **Source** | PostgreSQL — `trades` table |
| **Namespace** | `postgres.trades` |
| **File Name** | `trades_ingested_at={ts}_source=postgres.parquet` |
| **Ingestion Trigger** | `executed_at` > last_watermark |
| **Watermark Column** | `executed_at` (TIMESTAMPTZ) |

#### Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | `STRING` | UUID primary key |
| `order_id` | `STRING` | Order reference |
| `price` | `DECIMAL(18,8)` | Trade price |
| `quantity` | `DECIMAL(18,8)` | Trade quantity |
| `taker_side` | `STRING` | `buy` / `sell` |
| `executed_at` | `TIMESTAMPTZ` | Execution timestamp (watermark) |
| `created_at` | `TIMESTAMPTZ` | Record creation |
| `ingested_at` | `TIMESTAMPTZ` | ETL ingestion timestamp |
| `source` | `STRING` | Source identifier (`postgres`) |

---

### 3. MongoDB — Indodax Public API — Orderbooks (`orderbooks`)

| Property | Value |
|----------|-------|
| **Source** | MongoDB — `indodax.orderbooks` |
| **Namespace** | `mongodb.orderbooks` |
| **File Name** | `orderbooks_ingested_at={ts}_source=mongodb.parquet` |
| **Ingestion Trigger** | `ingested_at` > last_watermark |
| **Watermark Column** | `ingested_at` (UTC timestamp, ISO8601 string) |

#### Schema (Raw Envelope)

| Column | Type | Description |
|--------|------|-------------|
| `_id` | `STRING` | MongoDB ObjectId (hex string) |
| `event` | `STRING` | Event type (`depth` / `depth_update`) |
| `context` | `JSON` | Payload: `{pair, bids[], asks[]}` |
| `context.pair` | `STRING` | Trading pair |
| `context.bids` | `ARRAY<STRUCT<price:DECIMAL, quantity:DECIMAL, count:INT>>` | Bids |
| `context.asks` | `ARRAY<STRUCT<price:DECIMAL, quantity:DECIMAL, count:INT>>` | Asks |
| `ingested_at` | `TIMESTAMPTZ` | Ingestion timestamp (stored as ISO8601 string) |
| `source` | `STRING` | Source identifier (`mongodb`) |

#### Notes

- `context` field will be validated for structure only in Bronze; full semantic validation dilakukan di `staging/orderbooks.sql`.
- Timestamp `ingested_at` berasal dari Python ETL (bukan `event_timestamp`).

---

### 4. MongoDB — Indodax Public API — Tickers (`tickers`)

| Property | Value |
|----------|-------|
| **Source** | MongoDB — `indodax.tickers` |
| **Namespace** | `mongodb.tickers` |
| **File Name** | `tickers_ingested_at={ts}_source=mongodb.parquet` |
| **Ingestion Trigger** | `ingested_at` > last_watermark |
| **Watermark Column** | `ingested_at` (UTC timestamp, ISO8601 string) |

#### Schema (Raw Envelope)

| Column | Type | Description |
|--------|------|-------------|
| `_id` | `STRING` | MongoDB ObjectId (hex string) |
| `event` | `STRING` | Event type (`ticker`) |
| `context` | `JSON` | Payload: `{pair, base_volume, quote_volume, ...}` |
| `context.pair` | `STRING` | Trading pair |
| `context.base_volume` | `DECIMAL(18,8)` | 24h volume (base asset) |
| `context.quote_volume` | `DECIMAL(18,8)` | 24h volume (IDR) |
| `context.buy` | `DECIMAL(18,8)` | Buy order count |
| `context.sell` | `DECIMAL(18,8)` | Sell order count |
| `context.last_price` | `DECIMAL(18,8)` | Last traded price |
| `context.high` | `DECIMAL(18,8)` | 24h high |
| `context.low` | `DECIMAL(18,8)` | 24h low |
| `ingested_at` | `TIMESTAMPTZ` | Ingestion timestamp |
| `source` | `STRING` | Source identifier (`mongodb`) |

#### Notes

- Same validation approach as `orderbooks`.

---

## Watermark Storage — PostgreSQL `etl_watermark`

| Column | Type | Description |
|--------|------|-------------|
| `namespace` | `STRING` | Dataset namespace (e.g., `postgres.orders`, `mongodb.tickers`) |
| `source` | `STRING` | Source type (`postgres`, `mongodb`) |
| `last_watermark` | `TIMESTAMPTZ` | Last processed watermark value |
| `updated_at` | `TIMESTAMPTZ` | Last update timestamp |

---

## Ingestion Workflow

1. **Query Source** — Filter records where watermark column > last_watermark
2. **Add Metadata** — `ingested_at`, `source`
3. **Write Bronze** — Parquet to `s3://indodax-warehouse/bronze/{namespace}/`
4. **Update Watermark** — Set `last_watermark` = max(watermark column) dari data yang di-ingest

---

## Validation Rules

| Layer | Check | Method |
|-------|-------|--------|
| Bronze (MongoDB) | Top-level envelope structure | `event`, `context`, `ingested_at` must exist |
| Bronze (PostgreSQL) | Schema conformance | SQL constraints + DuckDB type coercion |
| Staging (dbt) | Semantic validation | Custom models (e.g., `staging/orderbooks.sql`) |

---

## Notes

- **No schema evolution** di Bronze layer. Jika source schema berubah, harus update ETL + re-ingest.
- **All timestamps** disimpan sebagai `TIMESTAMPTZ` (UTC).
- **Partisi bucket** — tidak ada bucketing untuk sementara (hanya partitioning).
