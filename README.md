# Automated Multi-Platform Posting (FastAPI)

`POST /posting` validates a message of at most 200 characters containing exactly one valid HTTP(S) link, then attempts to publish it concurrently to **Mastodon**, **Bluesky**, **DEV.to**, **Telegraph**, and **Blogger**. Each platform is handled independently, so a failure on one does not prevent the other attempts.

## Account and credential setup

| Platform | API documentation | Credentials |
|---|---|---|
| Mastodon | [Status API](https://docs.joinmastodon.org/methods/statuses/) | `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN` |
| Bluesky | [Create record API](https://docs.bsky.app/docs/api/com-atproto-repo-create-record) | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` |
| DEV.to | [Forem API](https://developers.forem.com/api/v1) | `DEVTO_API_KEY` |
| Telegraph | [Telegraph API](https://telegra.ph/api) | `TELEGRAPH_ACCESS_TOKEN` |
| Blogger | [Posts: insert](https://developers.google.com/blogger/docs/3.0/reference/posts/insert) | `BLOGGER_BLOG_ID`, `BLOGGER_ACCESS_TOKEN`; refresh credentials recommended |

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

### Telegraph

Telegraph API accounts are created through the API. Call `createAccount` with a `short_name` (and optionally an `author_name`) and copy `result.access_token` from the response into `TELEGRAPH_ACCESS_TOKEN`. The active adapter calls `createPage` with this token and returns the published page URL. Do not use a Telegram bot token here.

### Blogger

1. Enable the Blogger API in Google Cloud and create an OAuth 2.0 client. The app needs the `https://www.googleapis.com/auth/blogger` scope.
2. Authorize the Google account that owns the blog to obtain an access token and, when available, a refresh token. Blogger publishing requires OAuth; an API key alone is not sufficient.
3. Find the blog ID with the Blogger API for the authorized account and set it as `BLOGGER_BLOG_ID`.
4. Configure `BLOGGER_ACCESS_TOKEN` for the current access token. To allow this adapter to refresh an expired token, also set `BLOGGER_CLIENT_ID`, `BLOGGER_CLIENT_SECRET`, and `BLOGGER_REFRESH_TOKEN`.

The adapter publishes a public Blogger post with the message as its content, a title derived from the text, and a clickable CTA link. Token refresh is attempted when no access token is configured or Blogger returns HTTP 401. Token values remain your responsibility to store securely; a newly issued access token is used for that request and is not written back to `.env`.

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
    },
    {
      "platform": "Telegraph",
      "status": "success",
      "posted_url": "https://telegra.ph/...",
      "public_access": true,
      "date": "2026-11-18",
      "time": "07:30:00",
      "error": null
    },
    {
      "platform": "Blogger",
      "status": "failed",
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "Missing Blogger credentials: BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET, BLOGGER_REFRESH_TOKEN"
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

<img width="1792" height="1005" alt="image" src="https://github.com/user-attachments/assets/fdd64589-be52-42ed-8838-61c58558c650" />

