"""
Base Ingestion Framework

This module provides abstract base classes for all ingestion clients.
It ensures consistent pattern across PostgreSQL, MongoDB, and Indodax API
extraction with proper watermark management and error handling.

Design decisions:
- Base class enforces abstract methods for config, extract, and validation
- Watermark management is separate (watermark.py) to enable centralized control
- Retry policy lives in retry.py (shared backoff + transient classification)
- All I/O operations are async to support concurrent extraction
"""

import logging
from abc import ABC, abstractmethod
from .retry import is_transient, sleep_before_retry
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)



class BaseExtractor(ABC):
    """
    Abstract base class for all data extractors.

    Subclasses must implement:
    - _get_config(): Return configuration dict
    - _fetch_data(): Execute source-specific fetch logic
    - _validate_data(): Validate extracted data structure
    """

    def __init__(
        self,
        name: str,
        watermark_key: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30,
    ) -> None:
        """
        Initialize base extractor.

        Args:
            name: Extractor name (used for logging and metrics)
            watermark_key: Key to store watermark (e.g., "postgresql.orders")
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
        """
        self.name = name
        self.watermark_key = watermark_key
        self.max_retries = max_retries
        self.timeout = timeout
        self._config: Optional[Dict[str, Any]] = None

    @property
    @abstractmethod
    def config(self) -> Dict[str, Any]:
        """Return configuration for this extractor."""
        pass

    @abstractmethod
    async def _fetch_data(
        self,
        last_watermark: Optional[datetime] = None,
    ) -> Any:
        """
        Execute source-specific data fetch.

        Args:
            last_watermark: Last processed watermark value (None for full load)

        Returns:
            Extracted data (type depends on source)
        """
        pass

    @abstractmethod
    def _validate_data(self, data: Any) -> bool:
        """
        Validate extracted data structure.

        Args:
            data: Data to validate

        Returns:
            True if valid, raises exception otherwise
        """
        pass

    async def extract(
        self,
        last_watermark: Optional[datetime] = None,
    ) -> tuple[Any, datetime]:
        """
        Extract data with retry logic and validation.

        Args:
            last_watermark: Last processed watermark value

        Returns:
            Tuple of (extracted_data, max_watermark_from_data)

        Raises:
            ExtractionError: If all retries fail
        """
        last_attempt = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "%s: Attempt %d/%d - extracting data",
                    self.name,
                    attempt,
                    self.max_retries,
                )

                data = await self._fetch_data(last_watermark)

                if not self._validate_data(data):
                    raise ValueError(f"Validation failed for {self.name}")

                max_watermark = self._extract_max_watermark(data)

                logger.info(
                    "%s: Successfully extracted %d records",
                    self.name,
                    self._count_records(data),
                )

                return data, max_watermark

            except Exception as e:
                last_attempt = e
                logger.warning(
                    "%s: Attempt %d failed: %s",
                    self.name,
                    attempt,
                    str(e),
                )

                if not is_transient(e):
                    break

                if attempt < self.max_retries:
                    await sleep_before_retry(attempt, self.name)

        raise ExtractionError(
            f"{self.name}: All {self.max_retries} attempts failed"
        ) from last_attempt

    def _extract_max_watermark(self, data: Any) -> datetime:
        """Extract maximum watermark from data."""
        return datetime.now(timezone.utc)

    def _count_records(self, data: Any) -> int:
        """Count records in extracted data."""
        if isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            return sum(len(v) for v in data.values() if isinstance(v, list))
        return 0


class ExtractionError(Exception):
    """Raised when all extraction retries are exhausted."""
    pass
