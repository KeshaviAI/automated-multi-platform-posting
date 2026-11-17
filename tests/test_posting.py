import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.platforms.base import Platform, PlatformError, PostOutcome
from app.services import posting_service

client = TestClient(app)
OK = "Grow your visibility today. https://example.com"


def test_partial_failure_continues(monkeypatch):
    class Good(Platform):
        name = "Good"
        async def post(self, c, m, l):
            return PostOutcome(url="https://example.com/p/1")

    class Bad(Platform):
        name = "Bad"
        async def post(self, c, m, l):
            raise PlatformError("Authentication failed")

    async def fake_public(*_): return True
    monkeypatch.setattr(posting_service, "get_platforms", lambda: [Bad(), Good()])
    monkeypatch.setattr(posting_service, "_is_public", fake_public)

    r = client.post("/posting", json={"message": OK})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    bad, good = body["results"]
    assert good["status"] == "success" and good["public_access"] is True and good["error"] is None
    assert bad["status"] == "failed" and bad["error"] == "Authentication failed" and bad["posted_url"] is None


def test_all_fail_means_success_false(monkeypatch):
    class Boom(Platform):
        name = "Boom"
        async def post(self, c, m, l):
            raise RuntimeError("x")
    monkeypatch.setattr(posting_service, "get_platforms", lambda: [Boom()])
    assert client.post("/posting", json={"message": OK}).json()["success"] is False


@pytest.mark.parametrize("msg,fragment", [
    ("a" * 201 + " https://example.com", "exceed 200"),
    ("No link here", "exactly one"),
    ("Two https://a.com and https://b.com", "exactly one"),
    ("Bad link https://not_a_url", "Invalid URL"),
    ("Visit www.example.com", "http"),
    ("   ", "empty"),
])
def test_invalid_messages(msg, fragment):
    r = client.post("/posting", json={"message": msg})
    assert r.status_code == 422
    assert fragment in r.json()["errors"][0]["message"]


def test_missing_body_field():
    assert client.post("/posting", json={}).status_code == 422

