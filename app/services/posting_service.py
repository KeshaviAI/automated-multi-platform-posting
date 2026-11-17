import asyncio
import logging
from datetime import datetime, timezone
from typing import List

import httpx

from app.config import HTTP_TIMEOUT
from app.platforms import get_platforms
from app.platforms.base import Platform, PlatformError
from app.schemas import PlatformResult

log = logging.getLogger("posting")


async def _is_public(client: httpx.AsyncClient, url: str) -> bool:
    """Fetch the URL anonymously (no credentials) and check it resolves."""
    try:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 PostChecker"})
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def _describe_http_error(e: httpx.HTTPStatusError) -> str:
    body = e.response.text[:200].replace("\n", " ")
    hint = {401: "Authentication failed", 403: "Forbidden", 422: "Rejected by platform",
            429: "Rate limited"}.get(e.response.status_code, "HTTP error")
    return f"{hint} (HTTP {e.response.status_code}): {body}"


async def _post_one(
    client: httpx.AsyncClient,
    platform: Platform,
    message: str,
    link: str,
) -> PlatformResult:
    def failed(err: str) -> PlatformResult:
        return PlatformResult(platform=platform.name, status="failed", error=err)

    try:
        if missing := platform.missing_credentials():
            return failed(f"Missing credentials: {', '.join(missing)}")
        outcome = await platform.post(client, message, link)
        now = datetime.now(timezone.utc)
        public = outcome.public_access
        if outcome.url and public:
            public = await _is_public(client, outcome.url)
        return PlatformResult(
            platform=platform.name, status="success", posted_url=outcome.url, public_access=public,
            date=now.strftime("%Y-%m-%d"), time=now.strftime("%H:%M:%S"),
            error=outcome.error,
        )
    except httpx.HTTPStatusError as e:
        return failed(_describe_http_error(e))
    except httpx.TimeoutException:
        return failed("Request timed out")
    except httpx.HTTPError as e:
        return failed(f"Network error: {e}")
    except PlatformError as e:
        return failed(str(e))
    except Exception as e:  # one platform must never break the rest
        log.exception("Unexpected error on %s", platform.name)
        return failed(f"Unexpected error: {e}")


async def publish_all(
    message: str,
    link: str,
) -> List[PlatformResult]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        return list(await asyncio.gather(*(
            _post_one(client, p, message, link)
            for p in get_platforms()
        )))
