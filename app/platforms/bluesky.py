from datetime import datetime, timezone

from app.config import env
from app.platforms.base import Platform, PlatformError, PostOutcome

PDS = "https://bsky.social/xrpc"


class Bluesky(Platform):
    """Publish a post to Bluesky using an app password."""
    name = "Bluesky"
    required_env = ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"]

    async def post(self, client, message, link):
        session_response = await client.post(
            "{}/com.atproto.server.createSession".format(PDS),
            json={
                "identifier": env("BLUESKY_HANDLE"),
                "password": env("BLUESKY_APP_PASSWORD"),
            },
        )
        session_response.raise_for_status()
        session = session_response.json()
        access_jwt = session.get("accessJwt")
        did = session.get("did")
        handle = session.get("handle")
        if not access_jwt or not did or not handle:
            raise PlatformError("Bluesky session response is missing account details.")

        record = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        raw_message = message.encode("utf-8")
        link_bytes = link.encode("utf-8")
        byte_start = raw_message.find(link_bytes)
        if byte_start < 0:
            raise PlatformError("The CTA link could not be located in the message.")
        record["facets"] = [{
            "index": {
                "byteStart": byte_start,
                "byteEnd": byte_start + len(link_bytes),
            },
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
        }]

        post_response = await client.post(
            "{}/com.atproto.repo.createRecord".format(PDS),
            headers={"Authorization": "Bearer {}".format(access_jwt)},
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": record,
            },
        )
        post_response.raise_for_status()
        uri = post_response.json().get("uri")
        if not uri:
            raise PlatformError("No record URI returned by Bluesky.")
        rkey = uri.rsplit("/", 1)[-1]
        return PostOutcome(
            url="https://bsky.app/profile/{}/post/{}".format(handle, rkey)
        )
