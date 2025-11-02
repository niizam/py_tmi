from __future__ import annotations

from typing import Any, Optional

import httpx

DEFAULT_TIMEOUT = 10.0


async def fetch_json(url: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[Any]:
    """Fetch a JSON payload from the provided URL, returning None on error."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError):
        return None
