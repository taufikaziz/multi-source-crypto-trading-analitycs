"""
Unit tests for ingestion framework
"""

import pytest
from datetime import datetime, timezone
from src.ingestion.base import BaseExtractor, ExtractionError


def test_base_extractor_abstract_methods():
    """Test that BaseExtractor cannot be instantiated without abstract methods."""
    with pytest.raises(TypeError):
        BaseExtractor("test")
