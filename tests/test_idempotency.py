"""Tests for Pipeline Idempotency (Phase 19).

Verifies:
1. Back-to-back runs with unchanged source data do not emit duplicate Bronze files
   or corrupt/double-advance watermarks.
2. Deterministic object naming prevents uncontrolled file proliferation.
3. Rerunning with identical data produces consistent output and preserves watermark safety.
"""

import asyncio
from datetime import datetime, timezone
import pytest

import src.orchestration.tasks as tasks
from src.storage.minio import LocalStorage


@pytest.fixture
def mock_watermark_store():
    store = {}

    class MockWatermarkManager:
        def __init__(self, conn_string):
            self.conn_string = conn_string

        async def connect(self):
            pass

        async def close(self):
            pass

        async def get_all_watermarks(self):
            return dict(store)

        async def commit_watermarks(self, watermarks, source):
            store.update(watermarks)

    return store, MockWatermarkManager


def test_idempotent_watermark_advancement(mock_watermark_store, monkeypatch):
    """Running extraction twice without new source rows does not change watermark."""
    store, MockManager = mock_watermark_store
    monkeypatch.setattr(tasks, "WatermarkManager", MockManager)

    t1 = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 12, 13, 0, tzinfo=timezone.utc)

    # Initial state
    store["postgresql.orders"] = t1

    class MockExtractorFirstRun:
        def __init__(self, **kwargs):
            pass
        async def connect(self): pass
        async def close(self): pass
        async def extract(self, last_wm):
            return [{"order_id": "o1", "updated_at": t2}], t2

    monkeypatch.setattr(tasks, "PostgresExtractor", MockExtractorFirstRun)

    # Run 1: new data arrived
    datasets_1, watermarks_1 = asyncio.run(tasks.extract_postgres_data())
    asyncio.run(tasks.commit_source_watermarks("postgres", watermarks_1))
    assert store["postgresql.orders"] == t2

    # Run 2: no new data arrived
    class MockExtractorSecondRun:
        def __init__(self, **kwargs):
            pass
        async def connect(self): pass
        async def close(self): pass
        async def extract(self, last_wm):
            return [], last_wm

    monkeypatch.setattr(tasks, "PostgresExtractor", MockExtractorSecondRun)
    datasets_2, watermarks_2 = asyncio.run(tasks.extract_postgres_data())
    asyncio.run(tasks.commit_source_watermarks("postgres", watermarks_2))

    # Watermark remains at t2 (does not reset or jump forward artificially)
    assert store["postgresql.orders"] == t2
    assert datasets_2 == {}


def test_deterministic_bronze_partition_path():
    """Verify Bronze storage path adheres strictly to deterministic partitioning scheme."""
    storage = LocalStorage(base_path="data/bronze")
    path = storage.get_path(
        dataset="orders",
        ingestion_date="2026-09-12",
        hour="14",
        run_id="20260912T140000Z",
        source="postgresql",
    )
    assert path == "source=postgresql/dataset=orders/ingestion_date=2026-09-12/hour=14/orders_20260912T140000Z.json"


def test_empty_bronze_write_idempotency():
    """Writing empty datasets does not create empty/corrupt files."""
    paths = asyncio.run(
        tasks.write_source_bronze_data(
            source="postgresql",
            datasets={},
            captured_at=datetime.now(timezone.utc),
        )
    )
    assert paths == {}
