"""Integration tests: authorized data requests against the real gov API.

These exercise the path that currently 403s — a *data* request carrying the
bearer token. If auth is accepted, batch 1 returns rows; if the token is
rejected, `raise_for_status()` raises an HTTP 403 and the test fails loudly,
pinpointing the auth-on-data problem.
"""

import pytest

from gov_api_client.gov_client import GovClient

pytestmark = pytest.mark.integration


async def test_first_info_batch_is_authorized(gov_credentials: dict[str, str]) -> None:
    gov = GovClient(**gov_credentials)
    try:
        result = await gov._fetch_pfs_information(1)
        assert len(result.data) > 0
        assert result.data[0].node_id
    finally:
        await gov.close()


async def test_first_price_batch_is_authorized(gov_credentials: dict[str, str]) -> None:
    gov = GovClient(**gov_credentials)
    try:
        result = await gov._fetch_fuel_price(1)
        assert len(result.data) > 0
        assert result.data[0].node_id
    finally:
        await gov.close()


async def test_incremental_info_request_is_authorized(
    gov_credentials: dict[str, str],
) -> None:
    # an incremental request (with a timestamp) must also be accepted
    gov = GovClient(**gov_credentials)
    try:
        result = await gov._fetch_pfs_information(
            1, iso_timestamp="2020-01-01T00:00:00+00:00"
        )
        assert len(result.data) >= 0  # may be empty, but must not 403
    finally:
        await gov.close()
