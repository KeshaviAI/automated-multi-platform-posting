import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.platforms.base import PlatformError
from app.platforms.blogger import Blogger, TOKEN_URL
from app.platforms.bluesky import Bluesky
from app.platforms.devto import DevTo
from app.platforms.mastodon import Mastodon
from app.platforms.telegraph import Telegraph


def run_with_mock_client(platform, handler, *args):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await platform.post(client, *args)

    return asyncio.run(run())


def test_mastodon_publishes_public_status(monkeypatch):
    monkeypatch.setenv("MASTODON_BASE_URL", "https://mastodon.example")
    monkeypatch.setenv("MASTODON_ACCESS_TOKEN", "test-token")

    def handler(request):
        assert request.method == "POST"
        assert request.url == "https://mastodon.example/api/v1/statuses"
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.read() == (
            b'{"status":"Hello https://example.com","visibility":"public"}'
        )
        return httpx.Response(
            200, json={"url": "https://mastodon.example/@test/123"}
        )

    outcome = run_with_mock_client(
        Mastodon(), handler, "Hello https://example.com", "https://example.com"
    )
    assert outcome.url == "https://mastodon.example/@test/123"


def test_bluesky_creates_session_and_link_facet(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "test.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "test-app-password")
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("com.atproto.server.createSession"):
            assert request.read() == (
                b'{"identifier":"test.bsky.social","password":"test-app-password"}'
            )
            return httpx.Response(
                200,
                json={
                    "accessJwt": "test-jwt",
                    "did": "did:plc:test",
                    "handle": "test.bsky.social",
                },
            )

        assert request.url.path.endswith("com.atproto.repo.createRecord")
        assert request.headers["Authorization"] == "Bearer test-jwt"
        record = request.read().decode()
        assert '"uri":"https://example.com"' in record
        assert '"text":"Hello https://example.com"' in record
        assert '"byteStart":6' in record
        assert '"byteEnd":25' in record
        return httpx.Response(
            200,
            json={"uri": "at://did:plc:test/app.bsky.feed.post/record-key"},
        )

    outcome = run_with_mock_client(
        Bluesky(), handler, "Hello https://example.com", "https://example.com"
    )
    assert outcome.url == "https://bsky.app/profile/test.bsky.social/post/record-key"
    assert len(requests) == 2


def test_bluesky_facets_use_utf8_byte_offsets(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "test.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "test-app-password")
    message = "é https://example.com"

    def handler(request):
        if request.url.path.endswith("com.atproto.server.createSession"):
            return httpx.Response(
                200,
                json={
                    "accessJwt": "test-jwt",
                    "did": "did:plc:test",
                    "handle": "test.bsky.social",
                },
            )
        record = request.read().decode()
        assert '"byteStart":3' in record
        assert '"byteEnd":22' in record
        return httpx.Response(
            200,
            json={"uri": "at://did:plc:test/app.bsky.feed.post/record-key"},
        )

    run_with_mock_client(Bluesky(), handler, message, "https://example.com")


def test_platforms_include_mastodon_bluesky_devto_and_telegraph():
    from app.platforms import get_platforms

    assert [platform.name for platform in get_platforms()] == [
        "Mastodon", "Bluesky", "DEV.to", "Telegraph", "Blogger"
    ]


def test_devto_publishes_article(monkeypatch):
    monkeypatch.setenv("DEVTO_API_KEY", "test-api-key")

    def handler(request):
        assert request.method == "POST"
        assert request.url == "https://dev.to/api/articles"
        assert request.headers["api-key"] == "test-api-key"
        assert request.headers["Accept"] == "application/vnd.forem.api-v1+json"
        assert request.read() == (
            b'{"article":{"title":"A useful update",'
            b'"body_markdown":"A useful update https://example.com",'
            b'"published":true}}'
        )
        return httpx.Response(
            201, json={"url": "https://dev.to/test/a-useful-update-123"}
        )

    outcome = run_with_mock_client(
        DevTo(),
        handler,
        "A useful update https://example.com",
        "https://example.com",
    )
    assert outcome.url == "https://dev.to/test/a-useful-update-123"


def test_devto_uses_fallback_title_when_message_only_has_link(monkeypatch):
    monkeypatch.setenv("DEVTO_API_KEY", "test-api-key")

    def handler(request):
        assert b'"title":"A quick update"' in request.read()
        return httpx.Response(201, json={"url": "https://dev.to/test/post"})

    result = run_with_mock_client(
        DevTo(), handler, "https://example.com", "https://example.com"
    )
    assert result.url == "https://dev.to/test/post"


def test_telegraph_creates_public_page_with_clickable_link(monkeypatch):
    monkeypatch.setenv("TELEGRAPH_ACCESS_TOKEN", "test-token")
    message = "Hello https://example.com today"

    def handler(request):
        assert request.method == "POST"
        assert request.url == "https://api.telegra.ph/createPage"
        form = parse_qs(request.content.decode())
        assert form["access_token"] == ["test-token"]
        assert form["title"] == [message[:60]]
        content = json.loads(form["content"][0])
        assert content == [{
            "tag": "p",
            "children": [
                "Hello ",
                {
                    "tag": "a",
                    "attrs": {"href": "https://example.com"},
                    "children": ["https://example.com"],
                },
                " today",
            ],
        }]
        assert form["return_content"] == ["false"]
        return httpx.Response(
            200,
            json={"ok": True, "result": {"url": "https://telegra.ph/Test-11-18"}},
        )

    outcome = run_with_mock_client(
        Telegraph(), handler, message, "https://example.com"
    )
    assert outcome.url == "https://telegra.ph/Test-11-18"


def test_telegraph_api_error_is_reported(monkeypatch):
    monkeypatch.setenv("TELEGRAPH_ACCESS_TOKEN", "test-token")

    def handler(_):
        return httpx.Response(200, json={"ok": False, "error": "ACCESS_TOKEN_INVALID"})

    with pytest.raises(PlatformError, match="ACCESS_TOKEN_INVALID"):
        run_with_mock_client(
            Telegraph(), handler, "Hello https://example.com", "https://example.com"
        )


def test_blogger_publishes_post_with_link(monkeypatch):
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog-123")
    monkeypatch.setenv("BLOGGER_ACCESS_TOKEN", "access-token")

    def handler(request):
        assert request.method == "POST"
        assert request.url == (
            "https://www.googleapis.com/blogger/v3/blogs/blog-123/posts?isDraft=false"
        )
        assert request.headers["Authorization"] == "Bearer access-token"
        assert request.read() == (
            b'{"title":"A useful update",'
            b'"content":"A useful update <a href=\\"https://example.com\\">'
            b'https://example.com</a>"}'
        )
        return httpx.Response(
            200,
            json={"url": "https://example.blogspot.com/2026/11/a-useful-update.html"},
        )

    outcome = run_with_mock_client(
        Blogger(), handler, "A useful update https://example.com", "https://example.com"
    )
    assert outcome.url == "https://example.blogspot.com/2026/11/a-useful-update.html"


def test_blogger_refreshes_expired_access_token(monkeypatch):
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog-123")
    monkeypatch.setenv("BLOGGER_ACCESS_TOKEN", "expired-token")
    monkeypatch.setenv("BLOGGER_CLIENT_ID", "client-id")
    monkeypatch.setenv("BLOGGER_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("BLOGGER_REFRESH_TOKEN", "refresh-token")
    calls = []

    def handler(request):
        calls.append(request)
        if request.url == TOKEN_URL:
            assert request.content.decode() == (
                "client_id=client-id&client_secret=client-secret&"
                "refresh_token=refresh-token&grant_type=refresh_token"
            )
            return httpx.Response(200, json={"access_token": "new-access-token"})
        if request.headers["Authorization"] == "Bearer expired-token":
            return httpx.Response(401, json={"error": "invalid_token"})
        assert request.headers["Authorization"] == "Bearer new-access-token"
        return httpx.Response(
            200, json={"url": "https://example.blogspot.com/posted"}
        )

    outcome = run_with_mock_client(
        Blogger(), handler, "A useful update https://example.com", "https://example.com"
    )
    assert outcome.url == "https://example.blogspot.com/posted"
    assert len(calls) == 3
