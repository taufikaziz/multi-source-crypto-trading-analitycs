# Business Requirements — Multi-Source Crypto Trading Analytics

**Date:** 2026-09-12  
**Version:** v1.0

---

## Executive Summary

Platform ini dibangun untuk menjawab **6 business questions** yang menjadi KPI utama:

1. **Price Performance** — Bagaimana performa harga crypto setiap hari?
2. **Market Volume** — Crypto mana yang memiliki volume market terbesar?
3. **Trading Activity** — Bagaimana aktivitas trading berubah setiap hari?
4. **Price-Volume Correlation** — Bagaimana hubungan price movement dengan volume?
5. **User Activity** — Bagaimana aktivitas user berubah setiap hari?
6. **Business Metrics** — Apakah market activity berhubungan dengan trading/user activity?

---

## Business Questions → Data Requirements

### Question 1: Bagaimana performa harga crypto setiap hari?

**Objective:** Track daily price movements untuk setiap cryptocurrency.

**Required Columns:**

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `date` | DATE | Trading date | Silver/Gold |
| `symbol` | STRING | Crypto symbol (e.g., BTC, ETH) | Silver |
| `open_price` | DECIMAL | Opening price | Silver |
| `high_price` | DECIMAL | 24h high | Silver |
| `low_price` | DECIMAL | 24h low | Silver |
| `close_price` | DECIMAL | Closing price | Silver |
| `price_change_pct` | DECIMAL | % change vs previous day | Gold |

**Transformation:**

1. **Staging (dbt):** Parse Indodax `summaries` →标准化 timestamp, symbol
2. **Gold (dbt):** Aggregate by date + symbol, compute day-over-day change

**Target Model:** `gold_market_daily`

---

### Question 2: Crypto mana yang memiliki volume market terbesar?

**Objective:** Rank cryptocurrencies by trading volume.

**Required Columns:**

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `date` | DATE | Date | Silver/Gold |
| `symbol` | STRING | Crypto symbol | Silver |
| `total_volume_asset` | DECIMAL | Total volume in crypto | Silver |
| `total_volume_idr` | DECIMAL | Total volume in IDR | Silver |
| `volume_rank` | INT | Rank by volume | Gold |

**Transformation:**

1. **Staging:** Extract `base_volume`, `quote_volume` dari Indodax
2. **Gold:** Rank by `volume_idr`, compute aggregate daily totals

**Target Model:** `gold_trading_daily`

---

### Question 3: Bagaimana aktivitas trading berubah setiap hari?

**Objective:** Track daily trading activity metrics.

**Required Columns:**

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `date` | DATE | Date | Silver/Gold |
| `total_orders` | INT | Total orders executed | PostgreSQL |
| `completed_orders` | INT | Filled orders | PostgreSQL |
| `buy_volume` | DECIMAL | Total buy volume | PostgreSQL |
| `sell_volume` | DECIMAL | Total sell volume | PostgreSQL |
| `avg_trade_size` | DECIMAL | Average trade size | Gold |

**Transformation:**

1. **Staging:** Extract `orders`, `trades` dari PostgreSQL
2. **Intermediate:** Join orders + trades, compute daily aggregates
3. **Gold:** Compute buy/sell breakdown, average trade size

**Target Model:** `gold_trading_daily`

**Source:** PostgreSQL `orders`, `trades`

---

### Question 4: Bagaimana hubungan price movement dengan trading volume?

**Objective:** Analyze correlation between price and volume.

**Required Columns:**

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `date` | DATE | Date | Silver/Gold |
| `symbol` | STRING | Crypto symbol | Silver |
| `price_change_pct` | DECIMAL | Daily price change % | Gold |
| `volume_change_pct` | DECIMAL | Daily volume change % | Gold |
| `correlation_score` | DECIMAL | Price-volume correlation | Gold |

**Transformation:**

1. **Gold:** Join `gold_market_daily` + `gold_trading_daily`
2. Compute correlation metrics per symbol

**Target Model:** `gold_crypto_business_metrics`

**Source:** Indodax (via Silver) + PostgreSQL (via Silver)

---

### Question 5: Bagaimana aktivitas user berubah setiap hari?

**Objective:** Track daily user engagement metrics.

**Required Columns:**

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `date` | DATE | Date | Silver/Gold |
| `active_users` | INT | Users with activity | MongoDB |
| `market_views` | INT | User views of market page | MongoDB |
| `order_events` | INT | Order-related events | MongoDB |
| `login_events` | INT | Login events | MongoDB |

**Transformation:**

1. **Staging:** Extract `user_events` dari MongoDB, flatten nested `context`
2. **Intermediate:** Filter by event type, aggregate by date
3. **Gold:** Compute daily active users, event counts

**Target Model:** `gold_user_activity_daily`

**Source:** MongoDB `user_events`

---

### Question 6: Apakah market activity berhubungan dengan trading/user activity?

**Objective:** Multi-dimensional business metrics.

**Required Columns:**

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `date` | DATE | Date | Gold |
| `symbol` | STRING | Crypto symbol | Silver |
| `close_price` | DECIMAL | Closing price | Gold |
| `market_volume` | DECIMAL | Total market volume | Gold |
| `price_change_pct` | DECIMAL | Daily change % | Gold |
| `trading_volume` | DECIMAL | Trading volume | Gold |
| `total_orders` | INT | Total orders | Gold |
| `active_users` | INT | Daily active users | Gold |
| `market_views` | INT | Market page views | Gold |

**Transformation:**

1. **Gold:** Join `gold_market_daily`, `gold_trading_daily`, `gold_user_activity_daily`
2. Create unified business metrics table

**Target Model:** `gold_crypto_business_metrics`

---

## Data Sources Mapping

| Business Question | Primary Source | Secondary Source | Tertiary Source |
|-------------------|----------------|------------------|-----------------|
| Q1: Price Performance | Indodax (API) | — | — |
| Q2: Market Volume | Indodax (API) | — | — |
| Q3: Trading Activity | PostgreSQL (orders, trades) | — | — |
| Q4: Price-Volume | Indodax + PostgreSQL | — | — |
| Q5: User Activity | MongoDB (user_events) | — | — |
| Q6: Business Metrics | All sources | — | — |

---

## Gold Layer Schema (Final Target)

### `gold_market_daily`

```sql
date DATE NOT NULL
symbol STRING NOT NULL
open_price DECIMAL(18,8)
high_price DECIMAL(18,8)
low_price DECIMAL(18,8)
close_price DECIMAL(18,8)
price_change_pct DECIMAL(18,8)
volume_asset DECIMAL(18,8)
volume_idr DECIMAL(18,8)
PRIMARY KEY (date, symbol)
```

### `gold_trading_daily`

```sql
date DATE NOT NULL
symbol STRING NOT NULL
total_orders INT
completed_orders INT
buy_volume DECIMAL(18,8)
sell_volume DECIMAL(18,8)
trading_volume DECIMAL(18,8)
avg_trade_size DECIMAL(18,8)
PRIMARY KEY (date, symbol)
```

### `gold_user_activity_daily`

```sql
date DATE NOT NULL
active_users INT
market_views INT
order_events INT
login_events INT
PRIMARY KEY (date)
```

### `gold_crypto_business_metrics`

```sql
date DATE NOT NULL
symbol STRING NOT NULL
close_price DECIMAL(18,8)
market_volume DECIMAL(18,8)
price_change_pct DECIMAL(18,8)
trading_volume DECIMAL(18,8)
total_orders INT
active_users INT
market_views INT
PRIMARY KEY (date, symbol)
```

---

## Incremental Strategy

| Model | Strategy | Why |
|-------|----------|-----|
| `stg_*` | View | No state, always fresh |
| `int_*` | View/Ephemeral | Intermediate, no persistence |
| `gold_*` | Incremental + Merge | Large tables, avoid full refresh |

---

## Conclusion

6 business questions → 4 Gold models:

1. `gold_market_daily` — Q1, Q2
2. `gold_trading_daily` — Q3
3. `gold_user_activity_daily` — Q5
4. `gold_crypto_business_metrics` — Q4, Q6

Semua transformations akan diimplementasikan via dbt SQL models.
