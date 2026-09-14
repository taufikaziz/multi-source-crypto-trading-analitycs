"""Shared retry policy for async ingestion clients.

Phase 6: single source of truth for retry/backoff so per-source
clients (Indodax/Postgres/MongoDB) do not copy-paste retry loops.

- Transient errors (network/timeout/5xx/429-style): retry with
  exponential backoff.
- Code/data errors (ValueError/TypeError): do NOT retry, fail fast
  so Airflow surfaces the real error instead of burning retries.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_S = 1.0
DEFAULT_BACKOFF_CAP_S = 30.0

_NON_RETRYABLE = (ValueError, TypeError)


def compute_backoff(
    attempt: int,
    base_s: float = DEFAULT_BACKOFF_BASE_S,
    cap_s: float = DEFAULT_BACKOFF_CAP_S,
) -> float:
    return min(cap_s, base_s * (2 ** (attempt - 1)))


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, _NON_RETRYABLE):
        return False
    return True


async def sleep_before_retry(attempt: int, name: str = "") -> None:
    delay = compute_backoff(attempt)
    logger.info("%s: waiting %.1fs before retry", name or "extractor", delay)
    await asyncio.sleep(delay)