import json
from pathlib import Path


def inspect_summaries():
    bronze_path = Path("data/bronze/source=indodax/dataset=summaries")

    files = sorted(
        bronze_path.rglob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise FileNotFoundError(
            "No summaries JSON files found in Bronze layer."
        )

    latest_file = files[0]

    print(f"\nInspecting: {latest_file}")

    with latest_file.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    print("\n=== TOP-LEVEL KEYS ===")
    print(data.keys())

    for section_name in [
        "tickers",
        "prices_24h",
        "prices_7d",
    ]:
        section = data.get(section_name)

        print(f"\n=== {section_name.upper()} ===")

        if section is None:
            print("Section not found")
            continue

        print(f"Type: {type(section)}")
        print(f"Number of records: {len(section)}")

        first_key = next(iter(section), None)

        if first_key is not None:
            print(f"Sample key: {first_key}")
            print(f"Sample value: {section[first_key]}")


if __name__ == "__main__":
    inspect_summaries()