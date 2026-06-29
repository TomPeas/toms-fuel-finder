"""Integration test: real auth against the gov OAuth endpoint."""

import pytest

from gov_api_client.auth_client import AuthClient

pytestmark = pytest.mark.integration


async def test_get_token_returns_a_token(gov_credentials: dict[str, str]) -> None:
    client = AuthClient(**gov_credentials)
    try:
        token = await client.get_token()
        assert isinstance(token, str)
        assert token  # non-empty
    finally:
        await client.aclose()
