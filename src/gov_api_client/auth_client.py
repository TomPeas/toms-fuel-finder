from cachetools import TTLCache
from httpx import AsyncClient, HTTPError


class AuthError(Exception):
    pass


class AuthClient:
    def __init__(self, client_id: str, client_secret: str, base_url: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url
        self._client = AsyncClient(base_url=self._base_url)
        self._refresh_token_cache: TTLCache[str, str] = TTLCache(maxsize=1, ttl=172700)
        self._token_cache: TTLCache[str, str] = TTLCache(maxsize=1, ttl=3500)

    async def get_token(self) -> str:
        if self._token_cache.get("access_token") is not None:
            return self._token_cache["access_token"]
        if self._refresh_token_cache.get("refresh_token") is not None:
            token = await self._refresh_token()
        else:
            token = await self._fetch_token()
        self._token_cache["access_token"] = token
        return token

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
            data = response.json()
            self._refresh_token_cache["refresh_token"] = str(
                data["data"]["refresh_token"]
            )
            return str(data["data"]["access_token"])
        except HTTPError as e:
            raise AuthError("Failed to reach the authentication server.") from e

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
            data = response.json()
            self._refresh_token_cache["refresh_token"] = str(data["refresh_token"])
            return str(data["access_token"])
        except HTTPError as e:
            raise AuthError("Failed to reach the authentication server.") from e

    async def aclose(self) -> None:
        await self._client.aclose()
