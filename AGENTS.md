# Indodax Market Data Pipeline

This repository implements a multi-layered data architecture (Bronze to Silver to Gold) for processing cryptocurrency market data from Indodax exchange.

## Architecture Overview

### Layer Structure
- Bronze: Raw API responses stored as JSON files
- Silver: Cleaned, validated data stored as Parquet
- Gold: Business metrics derived from Silver layer

### Data Flow
Indodax API to Bronze (JSON) to Silver (Parquet) to Gold (Parquet) to Warehouse (DuckDB/Databricks)

## Key Conventions

### File Naming
- Module files follow layer naming: transformer.py, writer.py, loader.py, checks.py
- Schema definitions in schema.py
- Tests named test_module.py

### Data Transformations
- Silver: src/silver/transformer.py build_market_snapshot()
- Gold: src/gold/transformer.py build_market_metrics()
- Quality: src/quality/silver_checks.py and src/quality/gold_checks.py

### Warehouse
- Local: DuckDB at data/warehouse/indodax.duckdb
- Production: Databricks via src/warehouse/databricks_loader.py

## Important Notes

### Silver Transformer
The src/silver/transformer.py file is currently empty. When implementing:
- Accept pairs (list) and summaries (dict) from API
- Return a pandas DataFrame with standardized schema
- Include columns: pair_id, ticker_id, asset_name, prices, volumes, timestamps

### Databricks Authentication
1. If DATABRICKS_TOKEN is set auth_type=access-token
2. Otherwise auth_type=databricks-oauth (browser login)

### Airflow Docker Configuration
- Set PYTHONPATH=/opt/airflow/src in .env
- Ensure duckdb is installed in Docker image
- Configure consistent AIRFLOW__API__SECRET_KEY across containers
- Set actual Databricks connection values (not placeholders)

### Testing
Run tests with: pytest

## Project Structure
src/
├── bronze/        # Raw data ingestion
├── silver/        # Data transformation & validation
├── gold/          # Business metrics
├── quality/       # Data quality checks
├── warehouse/     # Data loading (DuckDB/Databricks)
├── ingestion/     # API client
└── orchestration/ # Pipeline orchestration

## Common Tasks

### Add New Data Quality Check
1. Add validation function to src/quality/layer_checks.py
2. Raise DataQualityError or GoldDataQualityError on failures
3. Import and call in the corresponding task

### Extend Pipeline
1. Add transformation logic to src/layer/transformer.py
2. Add validation in src/quality/layer_checks.py
3. Import functions in src/orchestration/tasks.py