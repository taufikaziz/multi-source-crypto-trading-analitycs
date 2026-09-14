from src.orchestration.tasks import (
    create_run_context,
    ingest_indodax_data,
    transform_gold_data,
    transform_silver_data,
)
from src.warehouse.databricks_loader import (
    DatabricksWarehouseLoader,
)


def main():
    context = create_run_context()

    captured_at = context["captured_at"]
    run_id = context["run_id"]

    pairs, summaries = ingest_indodax_data()

    gold_source_file = "databricks_loader_test"

    silver_df = transform_silver_data(
        pairs=pairs,
        summaries=summaries,
        captured_at=captured_at,
        summaries_path=gold_source_file,
        run_id=run_id,
    )

    gold_df = transform_gold_data(
        dataframe=silver_df,
    )

    loader = DatabricksWarehouseLoader()

    loader.load_market_snapshot(
        dataframe=gold_df,
    )

    print("Databricks warehouse load completed successfully.")

    print(f"Gold rows: {len(gold_df)}")


if __name__ == "__main__":
    main()