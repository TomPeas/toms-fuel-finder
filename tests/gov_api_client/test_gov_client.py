"""Unit tests for GovClient. The HTTP client and sub-fetches are mocked out.

These deliberately assert the behaviours that have regressed before:
- the singular fetches hit the *correct* endpoint (info vs prices),
- the incremental timestamp is forwarded as a query param,
- a 404 ends pagination (returns empty),
- pagination requests *contiguous* batches with no gaps,
- get_forecourt_data bootstraps full, then refreshes incrementally with the
  *previous* watermark.
"""

# Mock-based tests reassign methods and call into mocks; relax those strict checks.
# mypy: disable-error-code="method-assign, no-untyped-call"

from datetime import UTC, datetime, timedelta
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


def _response(payload: Any, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
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


# ── single-batch fetch: correct endpoint, params, parsing, 404 ───────────


async def test_fetch_pfs_information_hits_info_endpoint(
    sample_info: ForecourtInfo,
) -> None:
    gov = _make_gov()
    # the API returns a bare array, which the client parses as PFSInfoResponse(data=...)
    gov._http_client.get = AsyncMock(
        return_value=_response([sample_info.model_dump(mode="json")])
    )

    result = await gov._fetch_pfs_information(1)

    assert result.data[0].node_id == "n1"
    gov._http_client.get.assert_awaited_once_with(
        "/api/v1/pfs", params={"batch-number": 1}
    )


async def test_fetch_fuel_price_hits_prices_endpoint(
    sample_prices: ForecourtPrices,
) -> None:
    gov = _make_gov()
    gov._http_client.get = AsyncMock(
        return_value=_response([sample_prices.model_dump(mode="json")])
    )

    result = await gov._fetch_fuel_price(2)

    assert result.data[0].node_id == "n1"
    gov._http_client.get.assert_awaited_once_with(
        "/api/v1/pfs/fuel-prices", params={"batch-number": 2}
    )


async def test_fetch_includes_timestamp_when_incremental(
    sample_info: ForecourtInfo,
) -> None:
    gov = _make_gov()
    gov._http_client.get = AsyncMock(
        return_value=_response([sample_info.model_dump(mode="json")])
    )

    await gov._fetch_pfs_information(1, iso_timestamp="2026-02-17T16:00:00+00:00")

    gov._http_client.get.assert_awaited_once_with(
        "/api/v1/pfs",
        params={
            "batch-number": 1,
            "effective-start-timestamp": "2026-02-17T16:00:00+00:00",
        },
    )


async def test_fetch_404_returns_empty() -> None:
    gov = _make_gov()
    gov._http_client.get = AsyncMock(return_value=_response(None, status=404))

    result = await gov._fetch_pfs_information(99)

    assert result.data == []


# ── pagination: correct method, contiguous batches, stop on empty ────────


async def test_fetch_all_pfs_uses_info_method_not_prices() -> None:
    gov = _make_gov()
    gov._fetch_pfs_information = AsyncMock(return_value=PFSInfoResponse(data=[]))
    gov._fetch_fuel_price = AsyncMock(return_value=FuelPricesResponse(data=[]))

    await gov._fetch_all_pfs_information()

    gov._fetch_pfs_information.assert_awaited()  # the info method
    gov._fetch_fuel_price.assert_not_awaited()  # NOT the price method (regression)


async def test_fetch_all_prices_uses_price_method_not_info() -> None:
    gov = _make_gov()
    gov._fetch_fuel_price = AsyncMock(return_value=FuelPricesResponse(data=[]))
    gov._fetch_pfs_information = AsyncMock(return_value=PFSInfoResponse(data=[]))

    await gov._fetch_all_fuel_prices()

    gov._fetch_fuel_price.assert_awaited()
    gov._fetch_pfs_information.assert_not_awaited()


async def test_fetch_all_paginates_contiguously_and_stops(
    sample_info: ForecourtInfo,
) -> None:
    gov = _make_gov()

    def fake(batch_number: int, iso_timestamp: str | None = None) -> PFSInfoResponse:
        # batches 1..7 have data, everything after is empty (end of pages)
        if batch_number <= 7:
            return PFSInfoResponse(
                data=[sample_info.model_copy(update={"node_id": f"n{batch_number}"})]
            )
        return PFSInfoResponse(data=[])

    gov._fetch_pfs_information = AsyncMock(side_effect=fake)

    result = await gov._fetch_all_pfs_information()

    assert len(result.data) == 7
    requested = sorted(c.args[0] for c in gov._fetch_pfs_information.call_args_list)
    # contiguous from 1 with no gaps — guards against the batch-skip regression
    assert requested == list(range(1, max(requested) + 1))
    assert set(range(1, 8)).issubset(requested)


# ── _collect: merges info + prices into the flat forecourts dict ─────────


async def test_collect_merges_info_and_prices(
    sample_info: ForecourtInfo, sample_prices: ForecourtPrices
) -> None:
    gov = _make_gov()
    gov._fetch_all_pfs_information = AsyncMock(
        return_value=PFSInfoResponse(data=[sample_info])
    )
    gov._fetch_all_fuel_prices = AsyncMock(
        return_value=FuelPricesResponse(data=[sample_prices])
    )

    await gov._collect()

    assert "n1" in gov.forecourts
    merged = gov.forecourts["n1"]
    assert merged.postcode == "AB1 2CD"
    assert merged.prices == sample_prices.fuel_prices


# ── get_forecourt_data: bootstrap full, refresh incremental, filter ──────


async def test_get_forecourt_data_bootstraps_full_when_empty() -> None:
    gov = _make_gov()
    fc = _forecourt("n1")

    def populate(*args: object) -> None:
        gov.forecourts = {"n1": fc}

    gov._collect = AsyncMock(side_effect=populate)

    result = await gov.get_forecourt_data(None)

    gov._collect.assert_awaited_once_with()  # no timestamp = full bootstrap
    assert result == {"n1": fc}


async def test_get_forecourt_data_refreshes_with_previous_watermark() -> None:
    gov = _make_gov()
    gov.forecourts = {"n1": _forecourt("n1")}
    old = datetime.now(UTC) - timedelta(hours=2)
    gov._last_update = old
    gov._collect = AsyncMock()

    await gov.get_forecourt_data(None)

    # incremental refresh passes the PREVIOUS watermark, not "now"
    gov._collect.assert_awaited_once_with(old.isoformat())
    assert gov._last_update is not None and gov._last_update > old


async def test_get_forecourt_data_no_refresh_when_fresh() -> None:
    gov = _make_gov()
    gov.forecourts = {"n1": _forecourt("n1")}
    gov._last_update = datetime.now(UTC)
    gov._collect = AsyncMock()

    await gov.get_forecourt_data(None)

    gov._collect.assert_not_awaited()


async def test_get_forecourt_data_filters_by_ids() -> None:
    gov = _make_gov()
    fc1, fc2 = _forecourt("n1"), _forecourt("n2")
    gov.forecourts = {"n1": fc1, "n2": fc2}
    gov._last_update = datetime.now(UTC)
    gov._collect = AsyncMock()

    result = await gov.get_forecourt_data(["n2"])

    assert result == {"n2": fc2}


async def test_close_closes_both_clients() -> None:
    gov = _make_gov()
    gov._http_client.aclose = AsyncMock()
    gov._auth_client.aclose = AsyncMock()

    await gov.close()

    gov._http_client.aclose.assert_awaited_once()
    gov._auth_client.aclose.assert_awaited_once()
