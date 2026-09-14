"""
Bronze Layer Writer

This module provides atomic Bronze layer writes with support for both
MinIO object storage (primary) and local filesystem (fallback/testing).

Design decisions:
- MinIO-first: Default storage backend is MinIO (S3-compatible)
- Storage abstraction via src/storage/minio.py
- Configurable backend via BRONZE_STORAGE_BACKEND env var (defaults to "minio")
- All writes are async to support concurrent operations
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.storage.minio import BaseStorage, LocalStorage, MinIOStorage, get_storage

logger = logging.getLogger(__name__)


class BronzeWriter:
    """
    Writer for Bronze layer data.
    
    Defaults to MinIO object storage as primary target.
    Backend is configurable via BRONZE_STORAGE_BACKEND env var.
    """
    
    def __init__(
        self,
        base_path: Optional[str] = None,
        storage_backend: Optional[str] = None,
    ) -> None:
        """
        Initialize Bronze writer.
        
        Args:
            base_path: Base path for storage (default: "bronze" for MinIO or "data/bronze" for local)
            storage_backend: "minio" (default) or "local"
        """
        backend = storage_backend or os.getenv("BRONZE_STORAGE_BACKEND", "minio")
        self.backend = backend
        
        if backend == "local":
            self.base_path = Path(base_path or os.getenv("BRONZE_BASE_PATH", "data/bronze"))
            self._storage = LocalStorage(str(self.base_path))
        else:
            self.base_path = Path(base_path or os.getenv("BRONZE_MINIO_BASE_PATH", "bronze"))
            self._storage = MinIOStorage(
                base_path=str(self.base_path),
                endpoint=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
                access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
                secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
                bucket=os.getenv("MINIO_BUCKET", "indodax-data"),
            )
    
    async def write(
        self,
        dataset: str,
        data: Any,
        captured_at: Optional[datetime] = None,
        source: str = "indodax",
    ) -> str:
        """
        Atomically write a raw response to the Bronze layer.
        
        Args:
            dataset: Dataset name (e.g., "pairs", "summaries", "orders")
            data: Data to write
            captured_at: Timestamp for partitioning (default: now)
            source: Source system name (e.g., "indodax", "postgresql", "mongodb")
        
        Returns:
            Storage path (S3 URI or local path)
        """
        if captured_at is None:
            captured_at = datetime.now(timezone.utc)
        
        ingestion_date = captured_at.strftime("%Y-%m-%d")
        hour = captured_at.strftime("%H")
        run_id = captured_at.strftime("%Y%m%dT%H%M%SZ")
        
        path = self._storage.get_path(
            dataset=dataset,
            ingestion_date=ingestion_date,
            hour=hour,
            run_id=run_id,
            source=source,
        )
        
        storage_path = await self._storage.write(path, data)
        
        logger.info(
            "Bronze data written successfully: %s",
            storage_path,
        )
        
        return storage_path
    
    async def write_many(
        self,
        datasets: Dict[str, Any],
        captured_at: Optional[datetime] = None,
        source: str = "indodax",
    ) -> Dict[str, str]:
        """
        Write multiple datasets concurrently.
        
        Args:
            datasets: Dict of dataset_name -> data
            captured_at: Timestamp for partitioning (default: now)
            source: Source system name
        
        Returns:
            Dict of dataset_name -> storage_path
        """
        if captured_at is None:
            captured_at = datetime.now(timezone.utc)
        
        paths = await asyncio.gather(
            *[
                self.write(
                    dataset=name,
                    data=data,
                    captured_at=captured_at,
                    source=source,
                )
                for name, data in datasets.items()
            ]
        )
        return dict(zip(datasets.keys(), paths))
