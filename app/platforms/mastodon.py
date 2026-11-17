from app.config import env
from app.platforms.base import Platform, PlatformError, PostOutcome


class Mastodon(Platform):
    """Publish a public status to a Mastodon instance."""
    name = "Mastodon"
    required_env = ["MASTODON_BASE_URL", "MASTODON_ACCESS_TOKEN"]

    async def post(self, client, message, link):
        base_url = env("MASTODON_BASE_URL").rstrip("/")
        if not base_url.startswith(("https://", "http://")):
            raise PlatformError("MASTODON_BASE_URL must be an http(s) URL.")

        response = await client.post(
            "{}/api/v1/statuses".format(base_url),
            headers={"Authorization": "Bearer {}".format(env("MASTODON_ACCESS_TOKEN"))},
            json={"status": message, "visibility": "public"},
        )
        response.raise_for_status()
        data = response.json()
        url = data.get("url")
        if not url:
            raise PlatformError("No public status URL returned by Mastodon.")
        return PostOutcome(url=url)
