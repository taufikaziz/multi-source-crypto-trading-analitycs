"""
MongoDB Ingestion Client

Extracts event documents from MongoDB using Motor with watermark-based extraction.

Design decisions:
- Uses Motor for async MongoDB operations
- Watermark is `ingested_at` (not `event_timestamp` to handle out-of-order events)
- Returns raw document for Bronze layer storage
- Top-level envelope validation only; context validation in dbt staging
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseExtractor

logger = logging.getLogger(__name__)


class MongoDBExtractor(BaseExtractor):
    """
    Async MongoDB extractor using Motor.
    
    Supports watermark-based incremental extraction using `ingested_at`.
    """
    
    def __init__(
        self,
        uri: str,
        database: str,
        collection: str,
        namespace: str,
        max_retries: int = 3,
        timeout: int = 30,
    ) -> None:
        """
        Initialize MongoDB extractor.
        
        Args:
            uri: MongoDB connection URI
            database: Database name
            collection: Collection name
            namespace: Dataset namespace (e.g., "mongodb.user_events")
            max_retries: Maximum retry attempts
            timeout: Query timeout in seconds
        """
        super().__init__(
            name=f"mongodb.{collection}",
            watermark_key=namespace,
            max_retries=max_retries,
            timeout=timeout,
        )
        self.uri = uri
        self.database = database
        self.collection = collection
        self.namespace = namespace
        self._client = None
        self._db = None
        self._coll = None
    
    @property
    def config(self) -> Dict[str, Any]:
        """Return configuration for this extractor."""
        return {
            "uri": self.uri,
            "database": self.database,
            "collection": self.collection,
            "namespace": self.namespace,
        }
    
    async def connect(self) -> None:
        """Establish async MongoDB connection."""
        from motor.motor_asyncio import AsyncIOMotorClient
        self._client = AsyncIOMotorClient(self.uri)
        self._db = self._client[self.database]
        self._coll = self._db[self.collection]
    
    async def close(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
    
    async def _fetch_data(
        self,
        last_watermark: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch documents with optional watermark filter.
        
        Args:
            last_watermark: Last processed watermark value
        
        Returns:
            List of documents
        """
        filter_dict = {}
        if last_watermark:
            if isinstance(last_watermark, datetime):
                last_watermark = last_watermark.strftime("%Y-%m-%dT%H:%M:%SZ")
            filter_dict["ingested_at"] = {"$gt": last_watermark}
        
        cursor = self._coll.find(filter_dict).sort("ingested_at", 1)
        documents = await cursor.to_list(length=None)
        
        # Convert ObjectId to string for JSON serialization
        for doc in documents:
            doc["_id"] = str(doc["_id"])
        
        return documents
    
    def _validate_data(self, data: Any) -> bool:
        """Validate extracted data structure (top-level envelope only)."""
        if not isinstance(data, list):
            raise ValueError("Expected list of documents")
        
        required_fields = {"_id", "event", "context", "ingested_at"}
        
        for doc in data:
            missing = required_fields - set(doc.keys())
            if missing:
                raise ValueError(f"Document missing required fields: {missing}")
        
        return True
    
    def _extract_max_watermark(self, data: Any) -> datetime:
        """Extract maximum watermark from documents."""
        if not data:
            return datetime.now(timezone.utc)
        
        max_wm = max(
            datetime.fromisoformat(doc["ingested_at"].replace("Z", "+00:00"))
            for doc in data
            if doc.get("ingested_at")
        )
        
        return max_wm if max_wm else datetime.now(timezone.utc)
