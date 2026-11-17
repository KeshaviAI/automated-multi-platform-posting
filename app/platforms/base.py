from dataclasses import dataclass
from typing import List, Optional

import httpx


class PlatformError(Exception):
    """Expected, human-readable platform failure."""


@dataclass
class PostOutcome:
    url: Optional[str]
    public_access: bool = True
    error: Optional[str] = None


class Platform:
    name: str = "base"
    required_env: List[str] = []

    def missing_credentials(self) -> List[str]:
        from app.config import env
        return [k for k in self.required_env if not env(k)]

    async def post(
        self,
        client: httpx.AsyncClient,
        message: str,
        link: str,
    ) -> PostOutcome:
        raise NotImplementedError
