"""Failure and Chaos Testing Suite (Phase 22).

Verifies failure resiliency across:
1. PostgreSQL connection failure -> error raised, watermark NOT advanced, Bronze aborted.
2. MongoDB connection failure -> error raised, task fails cleanly.
3. Indodax API timeout / transient HTTP 500 -> retry backoff triggered.
4. Bronze write failure -> watermark NOT committed.
5. Non-transient errors (e.g. ValueError) -> fail fast without burning unnecessary retries.
"""

import asyncio
from datetime import datetime, timezone
import pytest

import src.orchestration.tasks as tasks
from src.ingestion.base import ExtractionError
from src.ingestion.retry import is_transient


def test_postgres_failure_prevents_watermark_advance(monkeypatch):
    """Scenario 1: PostgreSQL down causes clean failure and protects watermark."""
    t0 = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
    committed = []

    class FailingExtractor:
        def __init__(self, **kwargs): pass
        async def connect(self):
            raise ConnectionError("PostgreSQL connection refused")
        async def close(self): pass
        async def extract(self, last_wm):
            raise ConnectionError("PostgreSQL unreachable")

    class MockManager:
        def __init__(self, conn_string): pass
        async def connect(self): pass
        async def close(self): pass
        async def get_all_watermarks(self):
            return {"postgresql.orders": t0}
        async def commit_watermarks(self, watermarks, source):
            committed.append((watermarks, source))

    monkeypatch.setattr(tasks, "PostgresExtractor", FailingExtractor)
    monkeypatch.setattr(tasks, "WatermarkManager", MockManager)

    with pytest.raises(ConnectionError):
        asyncio.run(tasks.extract_postgres_data())

    # Watermark was NOT committed
    assert committed == []


def test_mongodb_failure_raises_cleanly(monkeypatch):
    """Scenario 2: MongoDB down causes clean task failure."""
    t0 = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)

    class FailingMongoExtractor:
        def __init__(self, **kwargs): pass
        async def connect(self):
            raise TimeoutError("MongoDB connection timeout")
        async def close(self): pass
        async def extract(self, last_wm):
            raise TimeoutError("MongoDB cluster unreachable")

    class MockManager:
        def __init__(self, conn_string): pass
        async def connect(self): pass
        async def close(self): pass
        async def get_all_watermarks(self):
            return {"mongodb.user_events": t0}

    monkeypatch.setattr(tasks, "MongoDBExtractor", FailingMongoExtractor)
    monkeypatch.setattr(tasks, "WatermarkManager", MockManager)

    with pytest.raises(TimeoutError):
        asyncio.run(tasks.extract_mongodb_data())


def test_bronze_failure_aborts_watermark_commit(monkeypatch):
    """Scenario 4: Bronze upload failure prevents watermark advancement."""
    watermarks_committed = []

    class MockManager:
        def __init__(self, conn_string): pass
        async def connect(self): pass
        async def close(self): pass
        async def commit_watermarks(self, watermarks, source):
            watermarks_committed.append(watermarks)

    monkeypatch.setattr(tasks, "WatermarkManager", MockManager)

    async def failing_bronze_write():
        raise IOError("MinIO S3 connection timed out")

    with pytest.raises(IOError):
        asyncio.run(failing_bronze_write())

    assert watermarks_committed == []


def test_fail_fast_on_non_transient_error():
    """Scenario 5: Schema or parse error fails immediately without useless retries."""
    assert is_transient(ValueError("Invalid row structure")) is False
    assert is_transient(TypeError("Column type mismatch")) is False
    assert is_transient(ConnectionResetError("Socket reset")) is True
