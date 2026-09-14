"""
Indodax Ingestion Client

Wrapper around existing indodax_client.py for consistent async ingestion pattern.

Design decisions:
- Reuses existing async aiohttp client
- Returns raw data (pairs, summaries) for Bronze storage
- Watermark handled by Bronze metadata (captured_at timestamp)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from .base import BaseExtractor

logger = logging.getLogger(__name__)


class IndodaxExtractor(BaseExtractor):
    """
    Async Indodax API extractor using existing indodax_client.
    
    Watermark is managed via Bronze metadata (captured_at timestamp).
    """
    
    def __init__(
        self,
        namespace_pairs: str = "indodax.pairs",
        namespace_summaries: str = "indodax.summaries",
        max_retries: int = 3,
        timeout: int = 30,
    ) -> None:
        """
        Initialize Indodax extractor.
        
        Args:
            namespace_pairs: Namespace for pairs dataset
            namespace_summaries: Namespace for summaries dataset
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
        """
        super().__init__(
            name="indodax",
            watermark_key=None,  # Indodax uses captured_at from Bronze
            max_retries=max_retries,
            timeout=timeout,
        )
        self.namespace_pairs = namespace_pairs
        self.namespace_summaries = namespace_summaries
        self._client = None
    
    @property
    def config(self) -> Dict[str, Any]:
        """Return configuration for this extractor."""
        return {
            "namespace_pairs": self.namespace_pairs,
            "namespace_summaries": self.namespace_summaries,
        }
    
    async def connect(self) -> None:
        """Initialize Indodax client (no-op, client is stateless)."""
        if self._client is None:
            from src.ingestion.indodax_client import IndodaxClient
            self._client = IndodaxClient(
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
    
    async def close(self) -> None:
        """Close Indodax client (no-op, client is stateless)."""
        pass
    
    async def _fetch_data(
        self,
        last_watermark: Optional[datetime] = None,
    ) -> Tuple[Any, Any]:
        """
        Fetch pairs and summaries from Indodax API.
        
        Args:
            last_watermark: Ignored for Indodax (no watermark in API)
        
        Returns:
            Tuple of (pairs, summaries)
        """
        if self._client is None:
            await self.connect()
        
        pairs, summaries = await self._client.fetch_all()
        return pairs, summaries
    
    def _validate_data(self, data: Any) -> bool:
        """Validate extracted data structure."""
        pairs, summaries = data
        
        if not isinstance(pairs, list):
            raise ValueError("pairs must be a list")
        if not isinstance(summaries, dict):
            raise ValueError("summaries must be a dict")
        if "tickers" not in summaries:
            raise ValueError("summaries must contain 'tickers' key")
        
        return True
    
    def _extract_max_watermark(self, data: Any) -> datetime:
        """Extract maximum watermark - always returns current UTC time."""
        return datetime.now(timezone.utc)
    
    def _count_records(self, data: Any) -> int:
        """Count records in extracted data."""
        pairs, summaries = data
        return len(pairs) + len(summaries.get("tickers", []))
