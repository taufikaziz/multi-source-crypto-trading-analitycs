import asyncio
import logging
import os
from pathlib import Path

import pandas as pd


logger = logging.getLogger(__name__)


class GoldWriter:
    def __init__(self, base_path: str = "data/gold") -> None:
        self.base_path = Path(base_path)

    async def write_market_metrics(
        self,
        dataframe: pd.DataFrame,
        ingestion_date: str,
        hour: str,
        run_id: str,
    ) -> Path:
        """
        Write a Gold Parquet file atomically.
        pandas.to_parquet is CPU/blocking I/O — offloaded to a thread
        executor so the event loop stays responsive during the write.
        """
        output_dir = (
            self.base_path
            / "dataset=market_metrics"
            / f"ingestion_date={ingestion_date}"
            / f"hour={hour}"
        )

        output_file = output_dir / f"market_metrics_{run_id}.parquet"
        temp_file = output_file.with_suffix(".tmp.parquet")

        loop = asyncio.get_running_loop()

        await loop.run_in_executor(None, lambda: output_dir.mkdir(parents=True, exist_ok=True))

        await loop.run_in_executor(
            None,
            lambda: dataframe.to_parquet(temp_file, index=False, engine="pyarrow"),
        )

        await loop.run_in_executor(None, lambda: os.replace(temp_file, output_file))

        logger.info("Gold data written successfully: %s", output_file)

        return output_file
