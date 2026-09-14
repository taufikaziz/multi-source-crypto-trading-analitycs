# Data Quality & Contract Testing Documentation (Phase 25)

## Testing Hierarchy
1. **Generic Schema Tests (`dbt_crypto_platform/models/**/schema.yml`)**:
   - `not_null` pada seluruh primary key, foreign key, dan timestamp utama.
   - `unique` pada entity identifier di level staging & marts.
   - `relationships` integritas referensial antar tabel relasional.
2. **Singular Business Tests (`dbt_crypto_platform/tests/*.sql`)**:
   - `test_orders_filled_quantity.sql`: Memastikan `filled_quantity <= quantity`.
   - `test_no_orphan_trades.sql`: Memastikan tidak ada trade tanpa order.
   - `test_account_balance_reconciliation.sql`: Memastikan balance non-negatif.
   - `test_positive_prices.sql`: Memastikan harga selalu `> 0`.
   - `test_non_negative_volumes.sql`: Memastikan volume transaksi `>= 0`.
   - `test_business_metric_consistency.sql`: Memastikan metrik bisnis valid dan konsisten.
