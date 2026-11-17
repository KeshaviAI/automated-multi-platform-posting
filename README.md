# Automated Multi-Platform Posting (FastAPI)

`POST /posting` validates a message of at most 200 characters containing exactly one valid HTTP(S) link, then attempts to publish it concurrently to **Mastodon**, **Bluesky**, and **DEV.to**. Each platform is handled independently, so a failure on one does not prevent the other attempts.

## Account and credential setup

| Platform | API documentation | Credentials |
|---|---|---|
| Mastodon | [Status API](https://docs.joinmastodon.org/methods/statuses/) | `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN` |
| Bluesky | [Create record API](https://docs.bsky.app/docs/api/com-atproto-repo-create-record) | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` |
| DEV.to | [Forem API](https://developers.forem.com/api/v1) | `DEVTO_API_KEY` |

### Mastodon

1. Create an account on a Mastodon instance (for example, [mastodon.social](https://mastodon.social/)). Your account belongs to the instance you choose.
2. Sign in, open **Preferences → Development**, and create an application.
3. Grant the `write:statuses` scope, save the application, and copy its access token.
4. Put the instance URL and token in `MASTODON_BASE_URL` and `MASTODON_ACCESS_TOKEN`.

### Bluesky

1. Create an account using the official [Bluesky app](https://bsky.app/) or an official signup route.
2. In the app, go to **Settings → Privacy and Security → App Passwords** and create an app password.
3. Set `BLUESKY_HANDLE` to your handle and `BLUESKY_APP_PASSWORD` to the generated app password. Do not use your main password.

### DEV.to

1. Create an account at [DEV Community](https://dev.to/).
2. Sign in and open your account settings, then find the **DEV Community API Keys** section (the exact settings path may change).
3. Generate an API key and set `DEVTO_API_KEY`.

The API publishes a short article with a generated title based on the message and the message as its Markdown body. This is article-style publishing rather than a short social status. Keep the API key in your local `.env`; never commit or share it.

If a platform credential is missing, that platform returns a failure result naming the missing environment variable while the other platforms are still attempted. Never put an account's main password in `.env`.

## Setup

Python 3.8 or later is supported.

```bash
python3 -m venv venv
source venv/bin/activate              # Windows: venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env                 # fill in the credentials
python -m uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Open the interactive API documentation at <http://localhost:4000/docs>.

## Request

```bash
curl -X POST http://localhost:4000/posting \
  -H "Content-Type: application/json" \
  -d '{"message":"Check out our latest platform: https://example.com"}'
```

## Response shape

Each result contains platform status, the returned post URL (when available), an anonymous public-access check, UTC posting date/time, and any error. The values below are illustrative; actual results depend on the platform API response and configured credentials.

```json
{
  "success": true,
  "results": [
    {
      "platform": "Mastodon",
      "status": "success",
      "posted_url": "https://mastodon.social/@user/123",
      "public_access": true,
      "date": "2026-11-16",
      "time": "10:30:00",
      "error": null
    },
    {
      "platform": "DEV.to",
      "status": "failed",
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "Missing credentials: DEVTO_API_KEY"
    }
  ]
}
```

Invalid input returns HTTP 422, for example:

```json
{
  "success": false,
  "errors": [
    {"field": "message", "message": "Message must contain exactly one CTA link (found 0)."}
  ]
}
```

## Tests

```bash
python -m pytest -q
```

Platform adapter tests use mocked HTTP responses and do not publish to real accounts. For live testing, use accounts and credentials you are authorized to use.
