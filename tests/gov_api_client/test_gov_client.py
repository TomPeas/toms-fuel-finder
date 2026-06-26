"""Unit tests for GovClient. The http client and auth client are mocked out."""

# Mock-based tests reassign methods and call into mocks; relax those strict checks.
# mypy: disable-error-code="method-assign, no-untyped-call"

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from gov_api_client.gov_client import GovClient
from gov_api_client.models import (
    Forecourt,
    ForecourtInfo,
    ForecourtPrices,
    FuelPricesResponse,
    PFSInfoResponse,
)


def _make_gov() -> GovClient:
    gov = GovClient(
        base_url="https://gov.test", client_id="cid", client_secret="csecret"
    )
    gov._http_client = AsyncMock()
    return gov


def _response(payload: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def _forecourt(node_id: str) -> Forecourt:
    return Forecourt(
        node_id=node_id,
        trading_name="S",
        postcode="AB1 2CD",
        latitude=1.0,
        longitude=2.0,
        prices=[],
    )


async def test_fetch_pfs_information_calls_endpoint(sample_info: ForecourtInfo) -> None:
    gov = _make_gov()
    payload = PFSInfoResponse(data=[sample_info]).model_dump(mode="json")
    gov._http_client.get = AsyncMock(return_value=_response(payload))

    result = await gov._fetch_pfs_information(1)

    assert result.data[0].node_id == "n1"
    gov._http_client.get.assert_awaited_once_with("/api/v1/pfs?batch-number=1")


async def test_fetch_fuel_price_calls_endpoint(sample_prices: ForecourtPrices) -> None:
    gov = _make_gov()
    payload = FuelPricesResponse(data=[sample_prices]).model_dump(mode="json")
    gov._http_client.get = AsyncMock(return_value=_response(payload))

    result = await gov._fetch_fuel_price(2)

    assert result.data[0].node_id == "n1"
    gov._http_client.get.assert_awaited_once_with(
        "/api/v1/pfs/fuel-prices?batch-number=2"
    )


async def test_fetch_all_pfs_information_paginates_until_empty(
    sample_info: ForecourtInfo,
) -> None:
    gov = _make_gov()
    page = PFSInfoResponse(data=[sample_info])
    empty = PFSInfoResponse(data=[])
    gov._fetch_pfs_information = AsyncMock(side_effect=[page, empty])

    result = await gov._fetch_all_pfs_information()

    assert len(result.data) == 1
    assert gov._fetch_pfs_information.await_count == 2


async def test_fetch_all_fuel_prices_paginates_until_empty(
    sample_prices: ForecourtPrices,
) -> None:
    gov = _make_gov()
    page = FuelPricesResponse(data=[sample_prices])
    empty = FuelPricesResponse(data=[])
    gov._fetch_fuel_price = AsyncMock(side_effect=[page, empty])

    result = await gov._fetch_all_fuel_prices()

    assert len(result.data) == 1
    assert gov._fetch_fuel_price.await_count == 2


async def test_get_forecourt_data_returns_all_when_ids_none() -> None:
    gov = _make_gov()
    fc = _forecourt("n1")
    gov.forecourts["data"] = {"n1": fc}
    gov.update = AsyncMock()

    result = await gov.get_forecourt_data(None)

    assert result == {"n1": fc}
    gov.update.assert_not_awaited()


async def test_get_forecourt_data_filters_by_ids() -> None:
    gov = _make_gov()
    fc1, fc2 = _forecourt("n1"), _forecourt("n2")
    gov.forecourts["data"] = {"n1": fc1, "n2": fc2}
    gov.update = AsyncMock()

    result = await gov.get_forecourt_data(["n2"])

    assert result == {"n2": fc2}


async def test_get_forecourt_data_updates_when_cache_empty() -> None:
    gov = _make_gov()
    fc = _forecourt("n1")

    def _populate(*args: object, **kwargs: object) -> None:
        gov.forecourts["data"] = {"n1": fc}

    gov.update = AsyncMock(side_effect=_populate)

    result = await gov.get_forecourt_data(None)

    gov.update.assert_awaited_once()
    assert result == {"n1": fc}


async def test_update_merges_info_and_prices(
    sample_info: ForecourtInfo, sample_prices: ForecourtPrices
) -> None:
    gov = _make_gov()
    gov._fetch_all_pfs_information = AsyncMock(
        return_value=PFSInfoResponse(data=[sample_info])
    )
    gov._fetch_all_fuel_prices = AsyncMock(
        return_value=FuelPricesResponse(data=[sample_prices])
    )

    await gov.update()

    merged = gov.forecourts["data"]["n1"]
    assert merged.postcode == "AB1 2CD"
    assert merged.prices == sample_prices.fuel_prices


async def test_close_closes_both_clients() -> None:
    gov = _make_gov()
    gov._http_client.aclose = AsyncMock()
    gov._auth_client.aclose = AsyncMock()

    await gov.close()

    gov._http_client.aclose.assert_awaited_once()
    gov._auth_client.aclose.assert_awaited_once()
