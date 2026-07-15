from asyncio import Lock
from typing import Any

from cachetools import TTLCache
from httpx import AsyncClient, HTTPStatusError, RequestError

from logging_config import HTTPX_EVENT_HOOKS, logger


class AuthError(Exception):
    pass


class AuthClient:
    def __init__(self, client_id: str, client_secret: str, base_url: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url
        self._client = AsyncClient(
            base_url=self._base_url, http2=True, event_hooks=HTTPX_EVENT_HOOKS
        )
        self._refresh_token_cache: TTLCache[str, str] = TTLCache(maxsize=1, ttl=172700)
        self._token_cache: TTLCache[str, str] = TTLCache(maxsize=1, ttl=3500)
        self._mutex = Lock()

    async def get_token(self) -> str:
        # fast path: no lock when the token is already cached (the common case)
        cached = self._token_cache.get("access_token")
        if cached is not None:
            return cached

        async with self._mutex:
            # re-check under the lock — someone may have refreshed while we waited
            cached = self._token_cache.get("access_token")
            if cached is not None:
                return cached

            if self._refresh_token_cache.get("refresh_token") is not None:
                token = await self._refresh_token()
            else:
                token = await self._fetch_token()

            self._token_cache["access_token"] = token
            return token

    def _store_tokens(self, data: dict[str, Any]) -> str:
        """Read tokens from the response's ``data`` envelope, cache the refresh
        token, and return the access token. Shared by fetch and refresh so the
        two can't parse different shapes."""
        tokens = data["data"]
        self._refresh_token_cache["refresh_token"] = str(tokens["refresh_token"])
        return str(tokens["access_token"])

    async def _fetch_token(self) -> str:
        try:
            response = await self._client.post(
                "/api/v1/oauth/generate_access_token",
                json={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            response.raise_for_status()
            return self._store_tokens(response.json())
        except HTTPStatusError as e:
            raise AuthError(
                f"Auth server returned HTTP {e.response.status_code}."
            ) from e
        except RequestError as e:
            logger.error("auth request failed: %s", e)
            raise AuthError("Could not reach the authentication server.") from e

    async def _refresh_token(self) -> str:
        try:
            response = await self._client.post(
                "/api/v1/oauth/regenerate_secret_token",
                json={
                    "client_id": self._client_id,
                    "refresh_token": self._refresh_token_cache["refresh_token"],
                },
            )
            response.raise_for_status()
            return self._store_tokens(response.json())
        except HTTPStatusError as e:
            raise AuthError(
                f"Auth server returned HTTP {e.response.status_code}."
            ) from e
        except RequestError as e:
            logger.error("auth request failed: %s", e)
            raise AuthError("Could not reach the authentication server.") from e

    async def aclose(self) -> None:
        await self._client.aclose()
