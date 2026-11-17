import re

from app.config import env
from app.platforms.base import Platform, PlatformError, PostOutcome


class DevTo(Platform):
    """Publish a short post as a DEV Community article."""
    name = "DEV.to"
    required_env = ["DEVTO_API_KEY"]

    async def post(self, client, message, link):
        title = re.sub(re.escape(link), "", message).strip(" \t\r\n.,;:!-")
        if not title:
            title = "A quick update"

        response = await client.post(
            "https://dev.to/api/articles",
            headers={
                "api-key": env("DEVTO_API_KEY"),
                "Accept": "application/vnd.forem.api-v1+json",
            },
            json={
                "article": {
                    "title": title[:100],
                    "body_markdown": message,
                    "published": True,
                }
            },
        )
        response.raise_for_status()
        url = response.json().get("url")
        if not url:
            raise PlatformError("No article URL returned by DEV.to.")
        return PostOutcome(url=url)
