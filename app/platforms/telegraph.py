import json

from app.config import env
from app.platforms.base import Platform, PlatformError, PostOutcome

API_URL = "https://api.telegra.ph"


class Telegraph(Platform):
    """Publish a public Telegraph page containing the message and CTA link."""
    name = "Telegraph"
    required_env = ["TELEGRAPH_ACCESS_TOKEN"]

    async def post(self, client, message, link):
        link_start = message.find(link)
        if link_start < 0:
            raise PlatformError("The CTA link could not be located in the message.")

        children = []
        before_link = message[:link_start]
        after_link = message[link_start + len(link):]
        if before_link:
            children.append(before_link)
        children.append({
            "tag": "a",
            "attrs": {"href": link},
            "children": [link],
        })
        if after_link:
            children.append(after_link)

        response = await client.post(
            "{}/createPage".format(API_URL),
            data={
                "access_token": env("TELEGRAPH_ACCESS_TOKEN"),
                "title": message[:60],
                "content": json.dumps([{"tag": "p", "children": children}]),
                "return_content": "false",
            },
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise PlatformError(data.get("error", "Telegraph rejected page creation."))
        url = data.get("result", {}).get("url")
        if not url:
            raise PlatformError("No page URL returned by Telegraph.")
        return PostOutcome(url=url)
