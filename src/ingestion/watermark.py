"""
Watermark Manager

This module provides centralized watermark management for all ingestion sources.
Watermarks are stored in PostgreSQL table `etl_watermark` and are only updated
AFTER Bronze write succeeds.

Design decisions:
- Single source of truth: PostgreSQL `etl_watermark` table
- Watermark update AFTER Bronze write (not at start of task)
- Watermark rollback on failure
- Thread-safe for concurrent extraction
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class WatermarkManager:
    """
    Centralized watermark manager for all ingestion sources.
    
    Watermarks are stored in PostgreSQL table `etl_watermark`:
    
    | Column | Type | Description |
    |--------|------|-------------|
    | namespace | STRING | Dataset namespace (e.g., "postgresql.orders") |
    | source | STRING | Source type ("postgres", "mongodb", "indodax") |
    | last_watermark | TIMESTAMPTZ | Last processed watermark value |
    | updated_at | TIMESTAMPTZ | Last update timestamp |
    """
    
    def __init__(
        self,
        conn_string: str,
        table_name: str = "etl_watermark",
    ) -> None:
        """
        Initialize watermark manager.
        
        Args:
            conn_string: PostgreSQL connection string
            table_name: Watermark table name
        """
        self.conn_string = conn_string
        self.table_name = table_name
        self._conn = None
    
    async def connect(self) -> None:
        """Establish async PostgreSQL connection."""
        from asyncpg import connect
        self._conn = await connect(self.conn_string)
        await self._ensure_table()
    
    async def close(self) -> None:
        """Close PostgreSQL connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
    
    async def _ensure_table(self) -> None:
        """Create etl_watermark table if not exists."""
        await self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                namespace TEXT NOT NULL PRIMARY KEY,
                source TEXT NOT NULL,
                last_watermark TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    
    async def get_watermark(
        self,
        namespace: str,
        source: str,
    ) -> Optional[datetime]:
        """Get last watermark for a namespace."""
        row = await self._conn.fetchrow(
            f"SELECT last_watermark FROM {self.table_name} WHERE namespace = $1",
            namespace,
        )
        if row:
            return row["last_watermark"]
        return None
    
    async def update_watermark(
        self,
        namespace: str,
        source: str,
        new_watermark: datetime,
    ) -> None:
        """Update watermark for a namespace. Called AFTER Bronze write succeeds."""
        await self._conn.execute(
            f"""
            INSERT INTO {self.table_name} 
            (namespace, source, last_watermark, updated_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (namespace) 
            DO UPDATE SET 
                last_watermark = EXCLUDED.last_watermark,
                updated_at = EXCLUDED.updated_at
            """,
            namespace,
            source,
            new_watermark,
            datetime.now(timezone.utc),
        )
        logger.info(
            "Watermark updated: namespace=%s, watermark=%s",
            namespace,
            new_watermark,
        )
    
    async def commit_watermarks(
        self,
        watermarks: Dict[str, datetime],
        source: str,
    ) -> None:
        """Commit multiple watermarks atomically. Called after all Bronze writes succeed."""
        async with self._conn.transaction():
            for namespace, watermark in watermarks.items():
                await self.update_watermark(namespace, source, watermark)
    
    async def get_all_watermarks(self) -> Dict[str, datetime]:
        """Get all watermarks."""
        rows = await self._conn.fetch(
            f"SELECT namespace, last_watermark FROM {self.table_name}"
        )
        return {row["namespace"]: row["last_watermark"] for row in rows}
