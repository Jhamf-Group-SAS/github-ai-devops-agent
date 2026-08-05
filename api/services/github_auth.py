"""
GitHub App authentication service.

Handles:
- JWT generation (app-level auth)
- Installation access token exchange (repo-level auth)
"""

import time
from functools import lru_cache
from pathlib import Path

import httpx
import jwt  # PyJWT
import structlog

from api.config import get_settings

logger = structlog.get_logger(__name__)

GITHUB_API_URL = "https://api.github.com"
JWT_EXPIRY_SECONDS = 600  # 10 minutes max per GitHub docs


class GitHubAuthService:
    def __init__(self, app_id: str, private_key: str) -> None:
        self._app_id = app_id
        self._private_key = private_key

    def _generate_jwt(self) -> str:
        """Generate a signed JWT for GitHub App authentication."""
        now = int(time.time())
        payload = {
            "iat": now - 60,  # issued 60s ago to allow clock skew
            "exp": now + JWT_EXPIRY_SECONDS,
            "iss": self._app_id,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    async def get_installation_token(self, installation_id: int) -> str:
        """Exchange app JWT for an installation access token."""
        app_jwt = self._generate_jwt()
        url = f"{GITHUB_API_URL}/app/installations/{installation_id}/access_tokens"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=10,
            )
            response.raise_for_status()

        token_data = response.json()
        logger.info("Installation token obtained", installation_id=installation_id)
        return token_data["token"]

    async def get_authenticated_client(self, installation_id: int) -> httpx.AsyncClient:
        """Return an httpx client pre-configured with an installation token."""
        token = await self.get_installation_token(installation_id)
        return httpx.AsyncClient(
            base_url=GITHUB_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )


def _load_private_key(settings) -> str:
    """
    Load the GitHub App private key.
    Priority:
      1. GITHUB_APP_PRIVATE_KEY_B64 env var (base64-encoded) — used in production/containers
      2. File at GITHUB_APP_PRIVATE_KEY_PATH — used in local dev
    """
    import base64
    import os

    b64 = os.environ.get("GITHUB_APP_PRIVATE_KEY_B64", "").strip()
    if b64:
        return base64.b64decode(b64).decode()

    key_path = Path(settings.github_app_private_key_path)
    if not key_path.exists():
        raise RuntimeError(
            "GitHub App private key not found. "
            "Set GITHUB_APP_PRIVATE_KEY_B64 or GITHUB_APP_PRIVATE_KEY_PATH."
        )
    return key_path.read_text()


@lru_cache
def get_github_auth_service() -> GitHubAuthService:
    settings = get_settings()

    if not settings.github_app_id:
        raise RuntimeError("GITHUB_APP_ID is not configured")

    private_key = _load_private_key(settings)
    return GitHubAuthService(app_id=settings.github_app_id, private_key=private_key)
