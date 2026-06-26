"""Unit tests for BearerAuth. The token provider is mocked out."""

from unittest.mock import AsyncMock

from httpx import Request

from gov_api_client.auth.bearer_auth import BearerAuth
from gov_api_client.auth_client import AuthClient


async def test_async_auth_flow_awaits_get_token_and_sets_header() -> None:
    provider = AsyncMock(spec=AuthClient)
    provider.get_token.return_value = "test_access_token"
    auth = BearerAuth(provider=provider)

    request = Request("GET", "https://test/data")
    flow = auth.async_auth_flow(request)
    authed = await flow.__anext__()  # advance to the `yield request`
    await flow.aclose()

    provider.get_token.assert_awaited_once()
    assert authed.headers["Authorization"] == "Bearer test_access_token"
