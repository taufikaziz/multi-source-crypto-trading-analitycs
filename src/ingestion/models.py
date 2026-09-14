"""Shared ingestion data models (Phase 6).

ExtractionMetadata is the standard audit record every extractor
produces. It feeds Phase 20 structured logging and Phase 19
run tracking without each client inventing its own dict shape.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


def new_run_id() -> str:
    return uuid4().hex[:12]


@dataclass
class ExtractionMetadata:
    run_id: str = field(default_factory=new_run_id)
    source: str = ""
    dataset: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    rows_extracted: int = 0
    watermark_before: Optional[datetime] = None
    watermark_after: Optional[datetime] = None
    status: str = "pending"
    duration_s: float = 0.0
    error: Optional[str] = None

    def finish(
        self,
        *,
        status: str,
        rows: int = 0,
        watermark_after: Optional[datetime] = None,
        error: Optional[str] = None,
    ) -> "ExtractionMetadata":
        self.end_time = datetime.now(timezone.utc)
        if self.start_time is not None:
            self.duration_s = (self.end_time - self.start_time).total_seconds()
        self.status = status
        self.rows_extracted = rows
        if watermark_after is not None:
            self.watermark_after = watermark_after
        self.error = error
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)