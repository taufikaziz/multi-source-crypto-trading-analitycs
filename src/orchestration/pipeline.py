import asyncio
import logging

from src.orchestration.tasks import (
    commit_source_watermarks,
    create_run_context,
    extract_mongodb_data,
    extract_postgres_data,
    ingest_indodax_data,
    load_data_warehouse,
    transform_gold_data,
    transform_silver_data,
    validate_gold_data,
    validate_silver_data,
    write_bronze_data,
    write_source_bronze_data,
    write_gold_data,
    write_silver_data,
)


logger = logging.getLogger(__name__)


async def run_pipeline() -> None:
    """
    Execute the complete Indodax market data pipeline asynchronously.

    Concurrency strategy:
      - Ingestion: Indodax API + PostgreSQL + MongoDB concurrently
      - Bronze writes (pairs + summaries JSON): parallel file writes
      - Silver write + Gold transform+validate: parallel (independent after silver transform)
      - Databricks load: runs in a thread executor (blocking driver)

    Stages that are sequential by necessity (data dependency):
      Ingest -> Bronze -> Silver transform -> Gold transform -> Warehouse load
    """

    # =========================
    # RUN CONTEXT
    # =========================

    context = create_run_context()
    captured_at = context["captured_at"]
    run_id = context["run_id"]

    logger.info("Starting pipeline run_id=%s", run_id)

    # =========================
    # INGESTION (Phase 7)
    # Indodax API + PostgreSQL tables + MongoDB collections run
    # concurrently. A source failure fails the run loudly: no Bronze
    # is written and no watermark advances for any source.
    # =========================

    indodax_result, postgres_result, mongo_result = await asyncio.gather(
        ingest_indodax_data(),
        extract_postgres_data(),
        extract_mongodb_data(),
    )
    pairs, summaries = indodax_result
    postgres_datasets, postgres_watermarks = postgres_result
    mongo_datasets, mongo_watermarks = mongo_result

    # =========================
    # BRONZE
    # All three sources written concurrently, then watermarks commit
    # (Phase 8: commit AFTER Bronze succeeds, never before).
    # =========================

    indodax_paths, postgres_paths, mongo_paths = await asyncio.gather(
        write_bronze_data(
            pairs=pairs,
            summaries=summaries,
            captured_at=captured_at,
        ),
        write_source_bronze_data(
            source="postgresql",
            datasets=postgres_datasets,
            captured_at=captured_at,
        ),
        write_source_bronze_data(
            source="mongodb",
            datasets=mongo_datasets,
            captured_at=captured_at,
        ),
    )
    pairs_path, summaries_path = indodax_paths

    await commit_source_watermarks(
        source="postgres",
        watermarks=postgres_watermarks,
    )
    await commit_source_watermarks(
        source="mongodb",
        watermarks=mongo_watermarks,
    )

    # =========================
    # SILVER
    # Transform is CPU-bound (sync), then validate + write async
    # =========================

    silver_df = transform_silver_data(
        pairs=pairs,
        summaries=summaries,
        captured_at=captured_at,
        summaries_path=summaries_path,
        run_id=run_id,
    )

    validate_silver_data(dataframe=silver_df)

    # =========================
    # GOLD TRANSFORM + SILVER WRITE
    # Gold transform is CPU-only and Silver write is I/O-only:
    # run them concurrently with asyncio.gather.
    # =========================

    loop = asyncio.get_running_loop()

    gold_transform_task = loop.run_in_executor(
        None,
        transform_gold_data,
        silver_df,
    )

    silver_write_task = write_silver_data(
        dataframe=silver_df,
        captured_at=captured_at,
        run_id=run_id,
    )

    gold_df, silver_path = await asyncio.gather(
        gold_transform_task,
        silver_write_task,
    )

    # =========================
    # GOLD VALIDATE + WRITE
    # =========================

    validate_gold_data(dataframe=gold_df)

    gold_path = await write_gold_data(
        dataframe=gold_df,
        captured_at=captured_at,
        run_id=run_id,
    )

    # =========================
    # WAREHOUSE
    # Blocking Databricks driver runs in thread executor
    # =========================

    await load_data_warehouse(dataframe=gold_df)

    # =========================
    # SUMMARY
    # =========================

    logger.info("Pipeline completed successfully.")
    logger.info("Bronze pairs:      %s", pairs_path)
    logger.info("Bronze summaries:  %s", summaries_path)
    for name, path in postgres_paths.items():
        logger.info("Bronze postgresql.%s: %s", name, path)
    for name, path in mongo_paths.items():
        logger.info("Bronze mongodb.%s: %s", name, path)
    logger.info("Silver snapshot:   %s", silver_path)
    logger.info("Gold metrics:      %s", gold_path)


def main() -> None:
    """Sync entrypoint — called by Airflow task or CLI."""
    asyncio.run(run_pipeline())
