"""Tests for Structured Logging and Observability (Phase 20).

Verifies:
1. Extraction metadata collects all required audit fields (run_id, source, dataset, rows, duration, status, watermarks).
2. Structured logs are emitted with key-value pairs parseable by log aggregators.
"""

import asyncio
import logging
from datetime import datetime, timezone
import pytest

from src.ingestion.models import ExtractionMetadata, new_run_id
import src.orchestration.tasks as tasks


def test_extraction_metadata_schema():
    """Metadata contains all audit attributes required by Phase 20."""
    t0 = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 12, 11, 0, tzinfo=timezone.utc)
    meta = ExtractionMetadata(
        run_id="run_123",
        source="postgres",
        dataset="trades",
        start_time=t0,
        watermark_before=t0,
    )
    meta.finish(status="success", rows=50, watermark_after=t1)

    record = meta.to_dict()
    assert record["run_id"] == "run_123"
    assert record["source"] == "postgres"
    assert record["dataset"] == "trades"
    assert record["rows_extracted"] == 50
    assert record["watermark_before"] == t0
    assert record["watermark_after"] == t1
    assert record["status"] == "success"
    assert record["duration_s"] >= 0.0


def test_structured_log_emission(caplog, monkeypatch):
    """Extraction pipeline emits structured key-value log messages."""
    t0 = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)

    class MockExtractor:
        def __init__(self, **kwargs): pass
        async def connect(self): pass
        async def close(self): pass
        async def extract(self, last_wm):
            return [{"id": 1}], t0

    class MockManager:
        def __init__(self, conn_string): pass
        async def connect(self): pass
        async def close(self): pass
        async def get_all_watermarks(self):
            return {"postgresql.users": t0}

    monkeypatch.setattr(tasks, "PostgresExtractor", MockExtractor)
    monkeypatch.setattr(tasks, "WatermarkManager", MockManager)

    with caplog.at_level(logging.INFO):
        asyncio.run(tasks.extract_postgres_data(run_id="audit_run_99"))

    messages = [rec.message for rec in caplog.records]
    matched = [m for m in messages if "run_id=audit_run_99" in m and "source=postgres" in m]
    assert len(matched) > 0
    assert "status=success" in matched[0]
