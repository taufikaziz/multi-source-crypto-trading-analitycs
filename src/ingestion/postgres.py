"""
PostgreSQL Ingestion Client

Extracts data from PostgreSQL using asyncpg with watermark-based incremental extraction.

Design decisions:
- Uses asyncpg for async PostgreSQL connection
- Watermark column is configurable (updated_at, executed_at, etc.)
- Returns raw data for Bronze layer storage
- Validation delegated to Bronze layer or dbt staging
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseExtractor

logger = logging.getLogger(__name__)


class PostgresExtractor(BaseExtractor):
    """
    Async PostgreSQL extractor using asyncpg.
    
    Supports watermark-based incremental extraction.
    """
    
    def __init__(
        self,
        conn_string: str,
        table: str,
        watermark_column: str,
        namespace: str,
        max_retries: int = 3,
        timeout: int = 30,
    ) -> None:
        """
        Initialize PostgreSQL extractor.
        
        Args:
            conn_string: PostgreSQL connection string
            table: Table name to extract
            watermark_column: Column to use for incremental extraction
            namespace: Dataset namespace (e.g., "postgresql.orders")
            max_retries: Maximum retry attempts
            timeout: Query timeout in seconds
        """
        super().__init__(
            name=f"postgres.{table}",
            watermark_key=namespace,
            max_retries=max_retries,
            timeout=timeout,
        )
        self.conn_string = conn_string
        self.table = table
        self.watermark_column = watermark_column
        self.namespace = namespace
        self._conn = None
    
    @property
    def config(self) -> Dict[str, Any]:
        """Return configuration for this extractor."""
        return {
            "conn_string": self.conn_string,
            "table": self.table,
            "watermark_column": self.watermark_column,
            "namespace": self.namespace,
        }
    
    async def connect(self) -> None:
        """Establish async PostgreSQL connection."""
        from asyncpg import connect
        self._conn = await connect(self.conn_string)
    
    async def close(self) -> None:
        """Close PostgreSQL connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
    
    async def _fetch_data(
        self,
        last_watermark: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch data with optional watermark filter.
        
        Args:
            last_watermark: Last processed watermark value
        
        Returns:
            List of row dictionaries
        """
        if last_watermark:
            query = f"""
                SELECT * FROM {self.table}
                WHERE {self.watermark_column} > $1
                ORDER BY {self.watermark_column} ASC
            """
            records = await self._conn.fetch(query, last_watermark)
        else:
            query = f"SELECT * FROM {self.table} ORDER BY {self.watermark_column} ASC"
            records = await self._conn.fetch(query)
        
        # Convert Row objects to dictionaries
        data = [dict(record) for record in records]
        return data
    
    def _validate_data(self, data: Any) -> bool:
        """Validate extracted data structure."""
        if not isinstance(data, list):
            raise ValueError("Expected list of records")
        return True
    
    def _extract_max_watermark(self, data: Any) -> datetime:
        """Extract maximum watermark from data."""
        if not data:
            return datetime.now(timezone.utc)
        
        max_wm = max(
            record.get(self.watermark_column)
            for record in data
            if record.get(self.watermark_column)
        )
        
        return max_wm if max_wm else datetime.now(timezone.utc)
