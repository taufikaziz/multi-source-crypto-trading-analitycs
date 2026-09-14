# Silver Layer Data Contract

**Date:** 2026-09-12  
**Version:** v1.0

---

## Overview

Silver layer adalah **staging layer** untuk dbt transformation. Tidak ada business logic di sini — hanya:

- Rename columns
- Cast tipe data
- Normalize struktur
- Deduplication dasar
- Source normalization

**Materialization:** View (non-materialized di dbt)

---

## Staging Models

### 1. `stg_indodax__pairs`

**Source:** Indodax `/api/pairs`

**Columns:**

| Column | Type | Source Field | Rule |
|--------|------|--------------|------|
| `pair_id` | STRING | `pair` | Raw string |
| `ticker_id` | STRING | `ticker_id` | Raw string |
| `asset_name` | STRING | `name` | Raw string |
| `base_currency` | STRING | `base_currency` | Raw string |
| `quote_currency` | STRING | `quote_currency` | Raw string |
| `price_decimal_places` | INT | `price_decimal_places` | Cast to INT |
| `min_price` | DECIMAL(18,8) | `min_price` | Cast to DECIMAL |
| `max_price` | DECIMAL(18,8) | `max_price` | Cast to DECIMAL |
| `min_volume` | DECIMAL(18,8) | `min_volume` | Cast to DECIMAL |
| `created_at` | TIMESTAMPTZ | `created_at` | Parse ISO8601 |

**Tests:**

```yaml
- not_null: pair_id
- unique: pair_id
- dbt_utils.expression_is_true:
    expression: "price_decimal_places >= 0"
```

---

### 2. `stg_indodax__summaries`

**Source:** Indodax `/api/summaries`

**Columns:**

| Column | Type | Source Field | Rule |
|--------|------|--------------|------|
| `pair_id` | STRING | `pair` | Raw string |
| `last_price` | DECIMAL(18,8) | `last` | Cast to DECIMAL |
| `buy_price` | DECIMAL(18,8) | `buy` | Cast to DECIMAL |
| `sell_price` | DECIMAL(18,8) | `sell` | Cast to DECIMAL |
| `high_price` | DECIMAL(18,8) | `high` | Cast to DECIMAL |
| `low_price` | DECIMAL(18,8) | `low` | Cast to DECIMAL |
| `volume_asset` | DECIMAL(18,8) | `vol_coin` | Cast to DECIMAL |
| `volume_idr` | DECIMAL(18,8) | `vol_idr` | Cast to DECIMAL |
| `price_24h_ago` | DECIMAL(18,8) | Derived | last / (1 + change_24h_pct/100) |
| `price_7d_ago` | DECIMAL(18,8) | Derived | last / (1 + change_7d_pct/100) |
| `captured_at` | TIMESTAMPTZ | `ingestion_timestamp` | Parse from Bronze metadata |
| `run_id` | STRING | `run_id` | From Bronze metadata |

**Tests:**

```yaml
- not_null: pair_id, last_price, buy_price, sell_price
- unique: [pair_id, captured_at]
- dbt_utils.expression_is_true:
    expression: "last_price > 0"
- dbt_utils.expression_is_true:
    expression: "high_price >= low_price"
- dbt_utils.expression_is_true:
    expression: "volume_idr >= 0"
```

---

### 3. `stg_postgres__users`

**Source:** PostgreSQL `users`

**Columns:**

| Column | Type | Rule |
|--------|------|------|
| `user_id` | STRING | UUID cast to STRING |
| `email` | STRING | Trim whitespace |
| `full_name` | STRING | Trim whitespace |
| `is_active` | BOOLEAN | Cast from database type |
| `created_at` | TIMESTAMPTZ | Keep original |
| `updated_at` | TIMESTAMPTZ | Keep original |
| `captured_at` | TIMESTAMPTZ | From watermark |

**Tests:**

```yaml
- not_null: user_id, email
- unique: user_id
- dbt_utils.expression_is_true:
    expression: "email LIKE '%@%'"  # Simple email validation
```

---

### 4. `stg_postgres__accounts`

**Source:** PostgreSQL `accounts`

**Columns:**

| Column | Type | Rule |
|--------|------|------|
| `account_id` | STRING | UUID cast to STRING |
| `user_id` | STRING | Foreign key to users |
| `currency` | STRING | Asset symbol |
| `balance` | DECIMAL(18,8) | NUMERIC → DECIMAL |
| `locked_balance` | DECIMAL(18,8) | NUMERIC → DECIMAL |
| `created_at` | TIMESTAMPTZ | Keep original |
| `updated_at` | TIMESTAMPTZ | Keep original |
| `captured_at` | TIMESTAMPTZ | From watermark |

**Tests:**

```yaml
- not_null: account_id, user_id, currency
- unique: account_id
- relationships:
    to: ref("stg_postgres__users")
    field: user_id
```

---

### 5. `stg_postgres__assets`

**Source:** PostgreSQL `assets`

**Columns:**

| Column | Type | Rule |
|--------|------|------|
| `asset_id` | STRING | UUID cast to STRING |
| `symbol` | STRING | Trim whitespace |
| `name` | STRING | Trim whitespace |
| `precision` | INT | Cast to INT |
| `created_at` | TIMESTAMPTZ | Keep original |

**Tests:**

```yaml
- not_null: asset_id, symbol
- unique: symbol  # Asset symbol should be unique
```

---

### 6. `stg_postgres__orders`

**Source:** PostgreSQL `orders`

**Columns:**

| Column | Type | Rule |
|--------|------|------|
| `order_id` | STRING | UUID cast to STRING |
| `user_id` | STRING | Foreign key to users |
| `pair` | STRING | Trading pair (Indodax symbol) |
| `order_type` | STRING | `buy` / `sell` |
| `price` | DECIMAL(18,8) | NUMERIC → DECIMAL |
| `quantity` | DECIMAL(18,8) | NUMERIC → DECIMAL |
| `filled_quantity` | DECIMAL(18,8) | NUMERIC → DECIMAL |
| `status` | STRING | `open` / `filled` / `cancelled` |
| `created_at` | TIMESTAMPTZ | Keep original |
| `updated_at` | TIMESTAMPTZ | Keep original (watermark) |
| `captured_at` | TIMESTAMPTZ | From watermark |

**Tests:**

```yaml
- not_null: order_id, user_id, pair, order_type, status
- unique: order_id
- dbt_utils.expression_is_true:
    expression: "filled_quantity <= quantity"
- dbt_utils.expression_is_true:
    expression: "price > 0"
- dbt_utils.expression_is_true:
    expression: "quantity > 0"
```

---

### 7. `stg_postgres__trades`

**Source:** PostgreSQL `trades`

**Columns:**

| Column | Type | Rule |
|--------|------|------|
| `trade_id` | STRING | UUID cast to STRING |
| `order_id` | STRING | Foreign key to orders |
| `price` | DECIMAL(18,8) | NUMERIC → DECIMAL |
| `quantity` | DECIMAL(18,8) | NUMERIC → DECIMAL |
| `taker_side` | STRING | `buy` / `sell` |
| `executed_at` | TIMESTAMPTZ | Keep original (watermark) |
| `captured_at` | TIMESTAMPTZ | From watermark |

**Tests:**

```yaml
- not_null: trade_id, order_id, price, quantity, taker_side
- unique: trade_id
- dbt_utils.expression_is_true:
    expression: "price > 0"
- dbt_utils.expression_is_true:
    expression: "quantity > 0"
```

---

### 8. `stg_postgres__transactions`

**Source:** PostgreSQL `transactions`

**Columns:**

| Column | Type | Rule |
|--------|------|------|
| `transaction_id` | STRING | UUID cast to STRING |
| `account_id` | STRING | Foreign key to accounts |
| `amount` | DECIMAL(18,8) | NUMERIC → DECIMAL |
| `type` | STRING | `deposit` / `withdrawal` |
| `status` | STRING | `pending` / `completed` / `failed` |
| `created_at` | TIMESTAMPTZ | Keep original |
| `captured_at` | TIMESTAMPTZ | From watermark |

**Tests:**

```yaml
- not_null: transaction_id, account_id, amount, type
- unique: transaction_id
- dbt_utils.accepted_values:
    field: type
    values: ["deposit", "withdrawal"]
```

---

### 9. `stg_mongodb__user_events`

**Source:** MongoDB `user_events`

**Columns:**

| Column | Type | Rule |
|--------|------|------|
| `event_id` | STRING | MongoDB `_id` cast to STRING |
| `event_type` | STRING | Required field |
| `user_id` | STRING | From `context.user_id` |
| `session_id` | STRING | From `context.session_id` |
| `event_timestamp` | TIMESTAMPTZ | From `context.timestamp` |
| `event_properties` | JSON | Full `context` object |
| `ingested_at` | TIMESTAMPTZ | From Bronze metadata |
| `captured_at` | TIMESTAMPTZ | From watermark |

**Tests:**

```yaml
- not_null: event_id, event_type
- unique: event_id
- dbt_utils.accepted_values:
    field: event_type
    values: ["market_view", "order_created", "login", "logout", "page_view"]
```

---

## Staging Rules

### Naming Convention

- Prefix: `stg_`
- Source: `{source_name}__{dataset_name}`
- Example: `stg_indodax__pairs`

### Type Casting

| Database Type | Target Type | Notes |
|---------------|-------------|-------|
| UUID | STRING | Cast to hex string |
| NUMERIC | DECIMAL(18,8) | Preserves precision |
| TIMESTAMP | TIMESTAMPTZ | Ensure UTC timezone |
| VARCHAR | STRING | Trim whitespace |
| BOOLEAN | BOOLEAN | Explicit cast |

### Watermark

- Semua staging models include `captured_at` (watermark from Bronze)
- Used for incremental processing di Silver layer

---

## Non-Goals (Staging Layer)

- ❌ No business aggregations
- ❌ No joins between sources
- ❌ No derived metrics
- ❌ No dimensional modeling

**Focus:** Clean, standardized data ready for transformation.

---

## Materialization

```yaml
# dbt_project.yml
models:
  crypto_platform:
    staging:
      +materialized: view  # Default untuk staging
```

---

## Conclusion

Silver layer = **Staging models in dbt**  
9 models (2 Indodax, 7 PostgreSQL, 1 MongoDB)  
Semua dengan tests di `schema.yml`

Ready to proceed ke dbt implementation.
