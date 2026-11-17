import asyncio

import httpx

from app.platforms.bluesky import Bluesky
from app.platforms.devto import DevTo
from app.platforms.mastodon import Mastodon


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


def test_platforms_include_only_mastodon_bluesky_and_devto():
    from app.platforms import get_platforms

    assert [platform.name for platform in get_platforms()] == [
        "Mastodon", "Bluesky", "DEV.to"
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
