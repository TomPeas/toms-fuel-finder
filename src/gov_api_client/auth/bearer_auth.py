from collections.abc import AsyncGenerator

from httpx import Auth, Request, Response

from gov_api_client.auth_client import AuthClient


class BearerAuth(Auth):
    def __init__(self, provider: AuthClient) -> None:
        self._provider = provider

    async def async_auth_flow(
        self, request: Request
    ) -> AsyncGenerator[Request, Response]:
        token = await self._provider.get_token()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request
