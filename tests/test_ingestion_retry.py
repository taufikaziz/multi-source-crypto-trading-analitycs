"""Unit tests for shared ingestion retry policy and metadata (Phase 6)."""

import pytest

from src.ingestion.retry import compute_backoff, is_transient
from src.ingestion.models import ExtractionMetadata, new_run_id


def test_backoff_is_exponential_with_cap():
    assert compute_backoff(1) == pytest.approx(1.0)
    assert compute_backoff(2) == pytest.approx(2.0)
    assert compute_backoff(3) == pytest.approx(4.0)
    assert compute_backoff(99) <= 30.0


def test_code_errors_are_not_transient():
    assert is_transient(ValueError("bad data")) is False
    assert is_transient(TypeError("bad type")) is False
    assert is_transient(ConnectionError("down")) is True
    assert is_transient(TimeoutError("slow")) is True


def test_metadata_finish_computes_duration():
    meta = ExtractionMetadata(source="postgres", dataset="orders")
    meta.finish(status="success", rows=10)
    assert meta.status == "success"
    assert meta.rows_extracted == 10
    assert meta.duration_s >= 0.0
    assert meta.end_time is not None


def test_run_ids_unique():
    assert new_run_id() != new_run_id()