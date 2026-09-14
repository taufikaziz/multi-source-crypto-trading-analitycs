import json
from pathlib import Path


def inspect_pairs_mapping():
    bronze_path = Path(
        "data/bronze/source=indodax/dataset=pairs"
    )

    files = sorted(
        bronze_path.rglob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise FileNotFoundError(
            "No pairs JSON files found in Bronze layer."
        )

    latest_file = files[0]

    print(f"\nInspecting: {latest_file}")

    with latest_file.open(
        "r",
        encoding="utf-8",
    ) as file:
        pairs = json.load(file)

    print(f"\nNumber of pairs: {len(pairs)}")

    print("\n=== FIRST 10 ID MAPPINGS ===")

    for pair in pairs[:10]:
        print(
            f"id={pair['id']:<15} "
            f"ticker_id={pair['ticker_id']:<15} "
            f"description={pair['description']}"
        )


if __name__ == "__main__":
    inspect_pairs_mapping()