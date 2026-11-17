import re
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator

from app.config import MAX_MESSAGE_LENGTH

URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
BARE_LINK_PATTERN = re.compile(r"(?<![/\w@.])www\.\S+", re.IGNORECASE)


def extract_urls(text: str) -> List[str]:
    return [u.rstrip(".,;:!?)\"'") for u in URL_PATTERN.findall(text)]


def is_valid_url(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        return False
    host = p.hostname or ""
    return bool(re.fullmatch(r"([a-z0-9-]+\.)+[a-z]{2,}", host, re.I)) or host == "localhost"


class PostRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message must not be empty.")
        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message must not exceed {MAX_MESSAGE_LENGTH} characters (got {len(v)})."
            )
        if BARE_LINK_PATTERN.search(v):
            raise ValueError("Links must start with http:// or https://.")
        urls = extract_urls(v)
        if len(urls) != 1:
            raise ValueError(f"Message must contain exactly one CTA link (found {len(urls)}).")
        if not is_valid_url(urls[0]):
            raise ValueError(f"Invalid URL: {urls[0]}")
        return v

    @property
    def link(self) -> str:
        return extract_urls(self.message)[0]


class PlatformResult(BaseModel):
    platform: str
    status: str  # "success" | "failed"
    posted_url: Optional[str] = None
    public_access: bool = False
    date: Optional[str] = None
    time: Optional[str] = None
    error: Optional[str] = None


class PostResponse(BaseModel):
    success: bool
    results: List[PlatformResult]
