"""Unit tests for ingestion framework."""

import pytest
from datetime import datetime, timezone

from src.ingestion.base import BaseExtractor, ExtractionError
from src.ingestion.watermark import WatermarkManager
from src.ingestion.postgres import PostgresExtractor
from src.ingestion.mongodb import MongoDBExtractor
from src.ingestion.indodax import IndodaxExtractor
from src.storage.minio import LocalStorage, MinIOStorage, get_storage


def test_import_base_extractor():
    """Test that base extractor can be imported."""
    assert BaseExtractor is not None
    assert ExtractionError is not None


def test_import_watermark_manager():
    """Test that watermark manager can be imported."""
    assert WatermarkManager is not None


def test_watermark_manager_instantiation():
    """Test that WatermarkManager can be instantiated."""
    wm = WatermarkManager(conn_string="postgresql://test:test@localhost:5432/test")
    assert wm.conn_string == "postgresql://test:test@localhost:5432/test"
    assert wm.table_name == "etl_watermark"


def test_import_postgres_extractor():
    """Test that postgres extractor can be imported."""
    assert PostgresExtractor is not None


def test_import_mongodb_extractor():
    """Test that mongodb extractor can be imported."""
    assert MongoDBExtractor is not None


def test_import_indodax_extractor():
    """Test that indodax extractor can be imported."""
    assert IndodaxExtractor is not None


def test_import_storage_backends():
    """Test that storage backends can be imported."""
    assert LocalStorage is not None
    assert MinIOStorage is not None
    assert get_storage is not None
