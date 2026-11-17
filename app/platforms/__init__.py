from typing import List

from app.platforms.base import Platform
from app.platforms.bluesky import Bluesky
from app.platforms.devto import DevTo
from app.platforms.mastodon import Mastodon


def get_platforms() -> List[Platform]:
    return [Mastodon(), Bluesky(), DevTo()]
