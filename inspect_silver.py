import pandas as pd


file_path = (
    "data/silver/"
    "dataset=market_snapshot/"
    "ingestion_date=2026-08-26/"
    "hour=04/"
    "market_snapshot_20260826T040308Z.parquet"
)

df = pd.read_parquet(file_path)

print("\n=== COLUMNS ===")
print(df.columns.tolist())

print("\n=== DTYPES ===")
print(df.dtypes)

print("\n=== TIMESTAMP SAMPLE ===")
print(
    df[
        [
            "pair_id",
            "captured_at",
        ]
    ].head()
)