# dbt Transformation & Modeling Documentation (Phase 25)

## Architecture Layers

```
MinIO Bronze (Parquet/JSON)
           │
           ▼
dbt Staging (Silver)       [9 models, Materialization: View]
           │
           ▼
dbt Intermediate           [5 models, Materialization: View]
           │
           ▼
dbt Marts (Gold)           [4 models, Materialization: Table]
```

## Models Breakdown
1. **Staging**: Pembersihan tipe data, standardisasi nama kolom, dan pemfilteran raw envelope JSON.
   - `stg_indodax__pairs`, `stg_indodax__summaries`
   - `stg_postgres__users`, `stg_postgres__accounts`, `stg_postgres__assets`, `stg_postgres__orders`, `stg_postgres__trades`, `stg_postgres__transactions`
   - `stg_mongodb__user_events`
2. **Intermediate**: Join dan normalisasi yang reusable tanpa logic presentasi bisnis:
   - `int_daily_market`, `int_daily_trading`, `int_orders_trades`, `int_user_events_daily`, `int_user_trading_activity`
3. **Marts / Gold**: Agregasi bisnis final berdimensi harian dengan materialisasi *table* (rebuild per run):
   - `gold_market_daily` (grain: `date` + `symbol`)
   - `gold_trading_daily` (grain: `date` + `symbol`)
   - `gold_user_activity_daily` (grain: `date`)
   - `gold_crypto_business_metrics` (grain: `date` + `symbol`)
