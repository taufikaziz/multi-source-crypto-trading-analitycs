# Databricks Analytical Warehouse Documentation (Phase 25)

## Overview
Databricks SQL Serverless / Pro Warehouse bertindak sebagai analytical layer utama untuk melayani kueri analitik, dashboard BI, dan reporting metrik bisnis.

## Catalog & Schema Structure
- **Catalog**: `workspace` (atau `crypto_platform` di cluster production)
- **Schemas**:
  - `staging`: Raw Delta tables dimuat dari Bronze layer
  - `intermediate`: View transformasi terintegrasi
  - `marts`: Tabel analitik Gold (`gold_crypto_business_metrics`, `gold_market_daily`, dll.)

## Deployment & Execution
Transformation dieksekusi secara native melalui adapter `dbt-databricks` menggunakan koneksi HTTP Path dan Token yang diinjeksikan via environment variables (`DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`).
