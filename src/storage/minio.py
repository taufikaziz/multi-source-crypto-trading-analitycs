import os

"""

Storage Abstraction Layer



This module provides a unified interface for writing Bronze data to

either local filesystem or MinIO object storage.



Design decisions:

- Abstract base class for storage backends

- MinIO uses S3-compatible API

- Atomic writes via temp file + rename

- Backward compatible with existing local filesystem usage

"""



import asyncio

import json

import logging

import uuid

from decimal import Decimal

import tempfile

from abc import ABC, abstractmethod

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Dict, Optional



import aiofiles

import aiofiles.os



logger = logging.getLogger(__name__)





def _json_default(value):

    if isinstance(value, datetime):

        return value.isoformat()

    if isinstance(value, Decimal):

        return float(value)

    if isinstance(value, uuid.UUID):

        return str(value)

    if type(value).__name__ == "ObjectId":

        return str(value)

    raise TypeError(

        f"Object of type {type(value).__name__} is not JSON serializable"

    )





class BaseStorage(ABC):

    """Abstract base class for storage backends."""

    

    def __init__(self, base_path: str) -> None:

        self.base_path = base_path

    

    @abstractmethod

    async def write(self, path: str, data: Any) -> str:

        """Write data to storage at specified path."""

        pass

    

    @abstractmethod

    async def write_many(self, files: Dict[str, Any]) -> Dict[str, str]:

        """Write multiple files to storage."""

        pass

    

    @abstractmethod

    def get_path(

        self,

        dataset: str,

        ingestion_date: str,

        hour: str,

        run_id: str,

        source: str = "indodax",

    ) -> str:

        """Generate storage path for Bronze file."""

        pass





class LocalStorage(BaseStorage):

    """Local filesystem storage backend."""

    

    async def write(self, path: str, data: Any) -> str:

        """Write data to local filesystem."""

        full_path = Path(self.base_path) / path

        loop = asyncio.get_running_loop()

        

        await loop.run_in_executor(

            None,

            lambda: full_path.parent.mkdir(parents=True, exist_ok=True),

        )

        

        await self._atomic_write(full_path, data)

        logger.info("Local file written: %s", full_path)

        return str(full_path)

    

    async def write_many(self, files: Dict[str, Any]) -> Dict[str, str]:

        """Write multiple files concurrently."""

        paths = await asyncio.gather(

            *[self.write(path, data) for path, data in files.items()]

        )

        return dict(zip(files.keys(), paths))

    

    async def _atomic_write(self, output_file: Path, data: Any) -> None:

        """Write JSON atomically with temp file + rename."""

        loop = asyncio.get_running_loop()

        payload = await loop.run_in_executor(

            None,

            lambda: json.dumps(data, ensure_ascii=False, indent=2, default=_json_default),

        )

        

        tmp_fd, tmp_path = tempfile.mkstemp(

            dir=output_file.parent,

            suffix=".tmp",

        )

        try:

            async with aiofiles.open(tmp_fd, mode="w", encoding="utf-8") as f:

                await f.write(payload)

            await aiofiles.os.replace(tmp_path, output_file)

        except Exception:

            await aiofiles.os.remove(tmp_path)

            raise

    

    def get_path(

        self,

        dataset: str,

        ingestion_date: str,

        hour: str,

        run_id: str,

        source: str = "indodax",

    ) -> str:

        """Generate local path for Bronze file."""

        return f"source={source}/dataset={dataset}/ingestion_date={ingestion_date}/hour={hour}/{dataset}_{run_id}.json"





class MinIOStorage(BaseStorage):

    """MinIO (S3-compatible) storage backend."""

    

    def __init__(

        self,

        base_path: str,

        endpoint: str = "http://minio:9000",

        access_key: str = "minioadmin",

        secret_key: str = "minioadmin",

        bucket: str = "indodax-data",

    ) -> None:

        super().__init__(base_path)

        self.endpoint = endpoint

        self.access_key = access_key

        self.secret_key = secret_key

        self.bucket = bucket

        self._client = None

    

    async def connect(self) -> None:

        """Initialize MinIO client."""

        import boto3

        self._client = boto3.client(

            "s3",

            endpoint_url=self.endpoint,

            aws_access_key_id=self.access_key,

            aws_secret_access_key=self.secret_key,

        )

        try:

            self._client.head_bucket(Bucket=self.bucket)

        except:

            self._client.create_bucket(Bucket=self.bucket)

    

    async def close(self) -> None:

        """Close MinIO client."""

        self._client = None

    

    async def write(self, path: str, data: Any) -> str:

        """Write data to MinIO with atomic upload."""

        if self._client is None:

            await self.connect()

        

        base = (self.base_path or "").strip("/")
        key = path.lstrip("/")
        if base and (key == base or key.startswith(base + "/")):
            s3_key = key
        elif base:
            s3_key = f"{base}/{key}"
        else:
            s3_key = key

        loop = asyncio.get_running_loop()

        

        temp_dir = Path(tempfile.gettempdir()) / "bronze_upload"

        temp_dir.mkdir(parents=True, exist_ok=True)

        

        temp_path = temp_dir / f"{path}.tmp"
        temp_path.parent.mkdir(parents=True, exist_ok=True)

        payload = await loop.run_in_executor(

            None,

            lambda: json.dumps(data, ensure_ascii=False, indent=2, default=_json_default),

        )

        

        async with aiofiles.open(temp_path, mode="w", encoding="utf-8") as f:

            await f.write(payload)

        

        await loop.run_in_executor(

            None,

            lambda: self._client.upload_file(str(temp_path), self.bucket, s3_key),

        )

        

        await loop.run_in_executor(None, lambda: temp_path.unlink())

        

        logger.info("MinIO file uploaded: s3://%s/%s", self.bucket, s3_key)

        return f"s3://{self.bucket}/{s3_key}"

    

    async def write_many(self, files: Dict[str, Any]) -> Dict[str, str]:

        """Write multiple files concurrently."""

        paths = await asyncio.gather(

            *[self.write(path, data) for path, data in files.items()]

        )

        return dict(zip(files.keys(), paths))

    

    def get_path(

        self,

        dataset: str,

        ingestion_date: str,

        hour: str,

        run_id: str,

        source: str = "indodax",

    ) -> str:

        """Generate S3 path for Bronze file."""

        return f"{source}/dataset={dataset}/ingestion_date={ingestion_date}/hour={hour}/{dataset}_{run_id}.json"





def get_storage(backend: Optional[str] = None, **kwargs) -> BaseStorage:

    """Factory function to get storage backend (defaults to MinIO)."""

    selected_backend = backend or os.getenv("BRONZE_STORAGE_BACKEND", "minio")

    if selected_backend == "minio":

        return MinIOStorage(

            base_path=kwargs.get("base_path", os.getenv("BRONZE_MINIO_BASE_PATH", "bronze")),

            endpoint=kwargs.get("endpoint", os.getenv("MINIO_ENDPOINT", "http://minio:9000")),

            access_key=kwargs.get("access_key", os.getenv("MINIO_ROOT_USER", "minioadmin")),

            secret_key=kwargs.get("secret_key", os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")),

            bucket=kwargs.get("bucket", os.getenv("MINIO_BUCKET", "indodax-data")),

        )

    return LocalStorage(base_path=kwargs.get("base_path", os.getenv("BRONZE_BASE_PATH", "data/bronze")))

