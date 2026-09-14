import asyncio
import logging
from typing import Any, Dict, List, Tuple

import aiohttp
from src.ingestion.retry import compute_backoff, is_transient, sleep_before_retry

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503, 504}


class IndodaxClient:
    BASE_URL = "https://indodax.com"

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ) -> None:
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def _get(
        self,
        session: aiohttp.ClientSession,
        endpoint: str,
    ) -> Any:
        url = f"{self.BASE_URL}{endpoint}"
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("Requesting data from %s (attempt %d/%d)", url, attempt, self.max_retries)
                async with session.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}) as response:
                    if response.status in _RETRY_STATUSES:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"HTTP status {response.status}",
                            headers=response.headers,
                        )
                    response.raise_for_status()
                    return await response.json(content_type=None)
            except Exception as exc:
                last_error = exc
                if not is_transient(exc) or attempt == self.max_retries:
                    raise
                await sleep_before_retry(attempt, f"IndodaxClient:{endpoint}")

        raise last_error

    async def fetch_all(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Fetch pairs and summaries concurrently in a single HTTP session.
        Both requests are independent so they run in parallel via asyncio.gather.
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            pairs, summaries = await asyncio.gather(
                self._get(session, "/api/pairs"),
                self._get(session, "/api/summaries"),
            )

        logger.info(
            "Ingestion completed: pairs=%s, tickers=%s",
            len(pairs),
            len(summaries.get("tickers", {})),
        )

        return pairs, summaries
