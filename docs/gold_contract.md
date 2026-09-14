# Gold Layer Data Contract

**Date:** 2026-09-12  
**Version:** v1.0

---

## Overview

Gold layer adalah **marts layer** untuk analytical business metrics. Ini adalah final output yang dipakai untuk:

- Dashboarding (BI tools)
- Analytics queries
- Business KPI tracking
- Machine learning features

**Materialization:** Table (incremental for large tables)

---

## Business Models

### 1. `gold_market_daily`

**Grain:** 1 row per date + symbol

**Purpose:** Track daily price performance untuk setiap cryptocurrency.

**Columns:**

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `date` | DATE | Trading date | From `stg_indodax__summaries.captured_at` |
| `symbol` | STRING | Crypto symbol (base currency) | From `stg_indodax__pairs.base_currency` |
| `open_price` | DECIMAL(18,8) | Opening price | Derived: last_price dari 00:00 UTC |
| `high_price` | DECIMAL(18,8) | 24h high | Aggregated from `stg_indodax__summaries` |
| `low_price` | DECIMAL(18,8) | 24h low | Aggregated from `stg_indodax__summaries` |
| `close_price` | DECIMAL(18,8) | Closing price | Last last_price dari 23:59 UTC |
| `price_change_pct` | DECIMAL(18,8) | % change vs previous day | Calculated |
| `price_change_7d_pct` | DECIMAL(18,8) | % change vs 7 days ago | Calculated |
| `volume_asset` | DECIMAL(18,8) | Total volume in base currency | Aggregated |
| `volume_idr` | DECIMAL(18,8) | Total volume in IDR | Aggregated |
| `created_at` | TIMESTAMPTZ | Model creation timestamp | Current timestamp |

**SQL Logic:**

```sql
-- Gold market daily aggregates
SELECT
    DATE(captured_at) AS date,
    p.base_currency AS symbol,
    FIRST_VALUE(last_price) OVER (PARTITION BY DATE(captured_at), p.base_currency ORDER BY captured_at) AS open_price,
    MAX(high_price) AS high_price,
    MIN(low_price) AS low_price,
    LAST_VALUE(last_price) OVER (PARTITION BY DATE(captured_at), p.base_currency ORDER BY captured_at ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS close_price,
    -- price change vs previous day
    (close_price - LAG(close_price) OVER (PARTITION BY p.base_currency ORDER BY DATE(captured_at))) / LAG(close_price) OVER (PARTITION BY p.base_currency ORDER BY DATE(captured_at)) * 100 AS price_change_pct,
    SUM(volume_idr) AS volume_idr,
    SUM(volume_asset) AS volume_asset
FROM {{ ref("stg_indodax__summaries") }} s
JOIN {{ ref("stg_indodax__pairs") }} p ON s.pair_id = p.pair_id
GROUP BY DATE(captured_at), p.base_currency
```

**Tests:**

```yaml
- not_null: date, symbol, close_price
- unique: [date, symbol]
- dbt_utils.expression_is_true:
    expression: "high_price >= low_price"
- dbt_utils.expression_is_true:
    expression: "price_change_pct >= -100 OR price_change_pct IS NULL"
```

---

### 2. `gold_trading_daily`

**Grain:** 1 row per date + symbol

**Purpose:** Track daily trading activity dan order metrics.

**Columns:**

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `date` | DATE | Date | From `stg_postgres__orders.updated_at` |
| `symbol` | STRING | Trading pair | From `stg_postgres__orders.pair` |
| `total_orders` | INT | Total orders placed | Count `stg_postgres__orders` |
| `completed_orders` | INT | Filled orders | Count WHERE status = `filled` |
| `buy_volume` | DECIMAL(18,8) | Total buy volume | SUM WHERE order_type = `buy` |
| `sell_volume` | DECIMAL(18,8) | Total sell volume | SUM WHERE order_type = `sell` |
| `trading_volume` | DECIMAL(18,8) | Total trading volume | SUM(t.quantity) |
| `avg_trade_size` | DECIMAL(18,8) | Average trade size | AVG(t.quantity) |
| `created_at` | TIMESTAMPTZ | Model creation timestamp | Current timestamp |

**SQL Logic:**

```sql
-- Gold trading daily
SELECT
    DATE(o.updated_at) AS date,
    o.pair AS symbol,
    COUNT(o.order_id) AS total_orders,
    COUNT(CASE WHEN o.status = 'filled' THEN 1 END) AS completed_orders,
    SUM(CASE WHEN o.order_type = 'buy' THEN o.quantity ELSE 0 END) AS buy_volume,
    SUM(CASE WHEN o.order_type = 'sell' THEN o.quantity ELSE 0 END) AS sell_volume,
    SUM(t.quantity) AS trading_volume,
    AVG(t.quantity) AS avg_trade_size
FROM {{ ref("stg_postgres__orders") }} o
LEFT JOIN {{ ref("stg_postgres__trades") }} t ON o.order_id = t.order_id
WHERE DATE(o.updated_at) IS NOT NULL
GROUP BY DATE(o.updated_at), o.pair
```

**Tests:**

```yaml
- not_null: date, symbol
- unique: [date, symbol]
- dbt_utils.expression_is_true:
    expression: "buy_volume + sell_volume > 0"
- dbt_utils.expression_is_true:
    expression: "completed_orders <= total_orders"
```

---

### 3. `gold_user_activity_daily`

**Grain:** 1 row per date

**Purpose:** Track daily user engagement metrics.

**Columns:**

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `date` | DATE | Date | From `stg_mongodb__user_events.event_timestamp` |
| `active_users` | INT | Users with any activity | COUNT(DISTINCT user_id) |
| `market_views` | INT | User views of market page | COUNT WHERE event_type = `market_view` |
| `order_events` | INT | Order-related events | COUNT WHERE event_type IN (`order_created`, ...) |
| `login_events` | INT | Login events | COUNT WHERE event_type = `login` |
| `created_at` | TIMESTAMPTZ | Model creation timestamp | Current timestamp |

**SQL Logic:**

```sql
-- Gold user activity daily
SELECT
    DATE(event_timestamp) AS date,
    COUNT(DISTINCT user_id) AS active_users,
    COUNT(CASE WHEN event_type = 'market_view' THEN 1 END) AS market_views,
    COUNT(CASE WHEN event_type IN ('order_created', 'order_updated') THEN 1 END) AS order_events,
    COUNT(CASE WHEN event_type = 'login' THEN 1 END) AS login_events
FROM {{ ref("stg_mongodb__user_events") }}
WHERE DATE(event_timestamp) IS NOT NULL
GROUP BY DATE(event_timestamp)
```

**Tests:**

```yaml
- not_null: date
- unique: date
- dbt_utils.expression_is_true:
    expression: "active_users >= 0"
- dbt_utils.expression_is_true:
    expression: "market_views + order_events + login_events >= active_users"
```

---

### 4. `gold_crypto_business_metrics`

**Grain:** 1 row per date + symbol

**Purpose:** Unified business metrics table untuk analytical queries.

**Columns:**

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `date` | DATE | Date | Join key |
| `symbol` | STRING | Crypto symbol | Join key |
| `close_price` | DECIMAL(18,8) | Closing price | From `gold_market_daily` |
| `market_volume` | DECIMAL(18,8) | Total market volume | From `gold_market_daily` |
| `price_change_pct` | DECIMAL(18,8) | Daily change % | From `gold_market_daily` |
| `trading_volume` | DECIMAL(18,8) | Total trading volume | From `gold_trading_daily` |
| `total_orders` | INT | Total orders | From `gold_trading_daily` |
| `active_users` | INT | Daily active users | From `gold_user_activity_daily` |
| `market_views` | INT | Market page views | From `gold_user_activity_daily` |
| `created_at` | TIMESTAMPTZ | Model creation timestamp | Current timestamp |

**SQL Logic:**

```sql
-- Gold crypto business metrics
SELECT
    m.date,
    m.symbol,
    m.close_price,
    m.volume_idr AS market_volume,
    m.price_change_pct,
    t.trading_volume,
    t.total_orders,
    u.active_users,
    u.market_views
FROM {{ ref("gold_market_daily") }} m
FULL OUTER JOIN {{ ref("gold_trading_daily") }} t ON m.date = t.date AND m.symbol = t.symbol
FULL OUTER JOIN {{ ref("gold_user_activity_daily") }} u ON m.date = u.date
```

**Tests:**

```yaml
- not_null: date, symbol, close_price
- unique: [date, symbol]
- dbt_utils.expression_is_true:
    expression: "market_volume >= 0"
- dbt_utils.expression_is_true:
    expression: "trading_volume >= 0"
```

---

## Materialization Strategy

| Model | Strategy | Reason |
|-------|----------|--------|
| `gold_market_daily` | `incremental` + `merge` | Large table, daily refresh |
| `gold_trading_daily` | `incremental` + `merge` | Large table, daily refresh |
| `gold_user_activity_daily` | `incremental` + `merge` | Large table, daily refresh |
| `gold_crypto_business_metrics` | `table` | Join table, smaller size |

**Example configuration:**

```yaml
# models/marts/gold_market_daily.yml
models:
  +materialized: incremental
  +incremental_strategy: merge
  +unique_key: [date, symbol]
  +merge_update_columns: ["high_price", "low_price", "close_price", "volume_idr", ...]
```

---

## Incremental Processing

### Watermark Strategy

| Model | Watermark Column | Logic |
|-------|------------------|-------|
| `gold_market_daily` | `MAX(captured_at)` dari `stg_indodax__summaries` | Incremental dari last run |
| `gold_trading_daily` | `MAX(updated_at)` dari `stg_postgres__orders` | Incremental dari last run |
| `gold_user_activity_daily` | `MAX(event_timestamp)` dari `stg_mongodb__user_events` | Incremental dari last run |

### Run Logic

```sql
-- gold_market_daily incremental
SELECT ... 
FROM stg_indodax__summaries
WHERE captured_at > (SELECT MAX(date) FROM gold_market_daily)
GROUP BY ...
```

---

## Databricks Schema

```sql
-- crypto_platform.marts.gold_market_daily
CREATE TABLE crypto_platform.marts.gold_market_daily (
    date DATE NOT NULL,
    symbol STRING NOT NULL,
    open_price DECIMAL(18,8),
    high_price DECIMAL(18,8),
    low_price DECIMAL(18,8),
    close_price DECIMAL(18,8),
    price_change_pct DECIMAL(18,8),
    volume_asset DECIMAL(18,8),
    volume_idr DECIMAL(18,8),
    created_at TIMESTAMP,
    PRIMARY KEY (date, symbol)
) USING DELTA
PARTITIONED BY (date);
```

---

## Conclusion

4 Gold models:

1. `gold_market_daily` — Price performance
2. `gold_trading_daily` — Trading activity
3. `gold_user_activity_daily` — User engagement
4. `gold_crypto_business_metrics` — Unified metrics

Semua dengan incremental materialization untuk efficiency.

Ready untuk dbt implementation.
