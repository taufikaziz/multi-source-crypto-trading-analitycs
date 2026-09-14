import os
from databricks import sql

token = os.getenv("DATABRICKS_TOKEN")
hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME")
http_path = os.getenv("DATABRICKS_HTTP_PATH")

conn = sql.connect(
    server_hostname=hostname,
    http_path=http_path,
    auth_type="access-token",
    access_token=token,
)
cursor = conn.cursor()

# Ensure schema exists
cursor.execute("CREATE SCHEMA IF NOT EXISTS workspace.indodax_market_data")

# Create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS workspace.indodax_market_data.dim_market (
    market_key BIGINT GENERATED ALWAYS AS IDENTITY,
    pair_id STRING NOT NULL,
    ticker_id STRING NOT NULL,
    asset_name STRING
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS workspace.indodax_market_data.dim_date (
    date_key INT NOT NULL,
    full_date DATE NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day INT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS workspace.indodax_market_data.fact_market_snapshot (
    market_key BIGINT,
    date_key INT,
    captured_at TIMESTAMP,
    run_id STRING,
    buy_price DOUBLE,
    sell_price DOUBLE,
    high_price DOUBLE,
    low_price DOUBLE,
    last_price DOUBLE,
    price_change_24h_pct DOUBLE,
    price_change_7d_pct DOUBLE,
    spread_pct DOUBLE,
    volume_asset DOUBLE,
    volume_idr DOUBLE,
    volume_rank BIGINT
)
""")

print("Databricks schema & tables created successfully.")
cursor.close()
conn.close()
