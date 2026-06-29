"""Unit tests for AuthClient. The httpx client is mocked out entirely."""

# Mock-based tests reassign methods and call into mocks; relax those strict checks.
# mypy: disable-error-code="method-assign, no-untyped-call"

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import HTTPError

from gov_api_client.auth_client import AuthClient, AuthError


def _make_client() -> AuthClient:
    client = AuthClient(
        client_id="cid", client_secret="csecret", base_url="https://auth.test"
    )
    client._client = AsyncMock()
    return client


def _response(payload: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


async def test_get_token_returns_cached_token() -> None:
    client = _make_client()
    client._token_cache["access_token"] = "cached"
    client._fetch_token = AsyncMock()
    client._refresh_token = AsyncMock()

    assert await client.get_token() == "cached"
    client._fetch_token.assert_not_awaited()
    client._refresh_token.assert_not_awaited()


async def test_get_token_fetches_when_no_token_or_refresh() -> None:
    client = _make_client()
    client._fetch_token = AsyncMock(return_value="fresh")
    client._refresh_token = AsyncMock()

    assert await client.get_token() == "fresh"
    client._fetch_token.assert_awaited_once()
    client._refresh_token.assert_not_awaited()
    assert client._token_cache["access_token"] == "fresh"


async def test_get_token_refreshes_when_refresh_token_present() -> None:
    client = _make_client()
    client._refresh_token_cache["refresh_token"] = "rt"
    client._fetch_token = AsyncMock()
    client._refresh_token = AsyncMock(return_value="refreshed")

    assert await client.get_token() == "refreshed"
    client._refresh_token.assert_awaited_once()
    client._fetch_token.assert_not_awaited()


async def test_fetch_token_posts_and_caches_refresh_token() -> None:
    client = _make_client()
    # token endpoint wraps the payload in a "data" envelope
    client._client.post = AsyncMock(
        return_value=_response({"data": {"access_token": "AT", "refresh_token": "RT"}})
    )

    token = await client._fetch_token()

    assert token == "AT"
    assert client._refresh_token_cache["refresh_token"] == "RT"
    client._client.post.assert_awaited_once_with(
        "/api/v1/oauth/generate_access_token",
        json={"client_id": "cid", "client_secret": "csecret"},
    )


async def test_fetch_token_raises_autherror_on_http_error() -> None:
    client = _make_client()
    resp = MagicMock()
    resp.raise_for_status.side_effect = HTTPError("boom")
    client._client.post = AsyncMock(return_value=resp)

    with pytest.raises(AuthError):
        await client._fetch_token()


async def test_refresh_token_posts_and_returns_access_token() -> None:
    client = _make_client()
    client._refresh_token_cache["refresh_token"] = "old_rt"
    client._client.post = AsyncMock(
        return_value=_response({"access_token": "AT2", "refresh_token": "new_rt"})
    )

    token = await client._refresh_token()

    assert token == "AT2"
    assert client._refresh_token_cache["refresh_token"] == "new_rt"
    client._client.post.assert_awaited_once_with(
        "/api/v1/oauth/regenerate_secret_token",
        json={"client_id": "cid", "refresh_token": "old_rt"},
    )


async def test_refresh_token_raises_autherror_on_http_error() -> None:
    client = _make_client()
    client._refresh_token_cache["refresh_token"] = "old_rt"
    resp = MagicMock()
    resp.raise_for_status.side_effect = HTTPError("boom")
    client._client.post = AsyncMock(return_value=resp)

    with pytest.raises(AuthError):
        await client._refresh_token()


async def test_aclose_closes_underlying_client() -> None:
    client = _make_client()
    client._client.aclose = AsyncMock()

    await client.aclose()

    client._client.aclose.assert_awaited_once()
