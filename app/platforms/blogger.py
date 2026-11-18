import html
import re
from urllib.parse import quote

from app.config import env
from app.platforms.base import Platform, PlatformError, PostOutcome

API_URL = "https://www.googleapis.com/blogger/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class Blogger(Platform):
    """Publish a public post to a Blogger blog using Google OAuth."""
    name = "Blogger"
    required_env = ["BLOGGER_BLOG_ID"]

    async def _refresh_access_token(self, client):
        client_id = env("BLOGGER_CLIENT_ID")
        client_secret = env("BLOGGER_CLIENT_SECRET")
        refresh_token = env("BLOGGER_REFRESH_TOKEN")
        missing = [
            name for name, value in (
                ("BLOGGER_CLIENT_ID", client_id),
                ("BLOGGER_CLIENT_SECRET", client_secret),
                ("BLOGGER_REFRESH_TOKEN", refresh_token),
            )
            if not value
        ]
        if missing:
            raise PlatformError(
                "Missing Blogger credentials: {}".format(", ".join(missing))
            )

        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        access_token = response.json().get("access_token")
        if not access_token:
            raise PlatformError("Google OAuth response did not include an access token.")
        return access_token

    @staticmethod
    def _content(message, link):
        before, separator, after = message.partition(link)
        if not separator:
            raise PlatformError("The CTA link could not be located in the message.")
        return "{}<a href=\"{}\">{}</a>{}".format(
            html.escape(before),
            html.escape(link, quote=True),
            html.escape(link),
            html.escape(after),
        )

    async def post(self, client, message, link):
        blog_id = env("BLOGGER_BLOG_ID")
        if not blog_id:
            raise PlatformError("Missing Blogger credential: BLOGGER_BLOG_ID")

        title = re.sub(re.escape(link), "", message).strip(" \t\r\n.,;:!-")
        if not title:
            title = "A quick update"

        access_token = env("BLOGGER_ACCESS_TOKEN")
        if not access_token:
            access_token = await self._refresh_access_token(client)

        endpoint = "{}/blogs/{}/posts".format(API_URL, quote(blog_id, safe=""))
        headers = {"Authorization": "Bearer {}".format(access_token)}
        payload = {"title": title[:100], "content": self._content(message, link)}
        response = await client.post(
            endpoint,
            headers=headers,
            params={"isDraft": "false"},
            json=payload,
        )

        if response.status_code == 401 and env("BLOGGER_REFRESH_TOKEN"):
            access_token = await self._refresh_access_token(client)
            response = await client.post(
                endpoint,
                headers={"Authorization": "Bearer {}".format(access_token)},
                params={"isDraft": "false"},
                json=payload,
            )

        response.raise_for_status()
        url = response.json().get("url")
        if not url:
            raise PlatformError("No published post URL returned by Blogger.")
        return PostOutcome(url=url)
