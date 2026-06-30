"""Integration tests: postcode lookup + end-to-end station search.

FuelFinderClient imports `config` (which reads env at import time), so it's
imported *inside* the tests — after the credentials fixture has confirmed the
env is present — rather than at module top.
"""

import pytest

pytestmark = pytest.mark.integration

# rough UK bounding box for sanity-checking resolved coordinates
_UK_LAT = (49.0, 61.0)
_UK_LON = (-8.0, 2.0)


async def test_postcode_resolves_to_coords(gov_credentials: dict[str, str]) -> None:
    from fuel_finder_client.fuel_finder_client import FuelFinderClient

    client = FuelFinderClient()
    lat, lon = await client._get_coords("CM2 9JT")
    assert _UK_LAT[0] < lat < _UK_LAT[1]
    assert _UK_LON[0] < lon < _UK_LON[1]


async def test_get_returns_stations(gov_credentials: dict[str, str]) -> None:
    # full end-to-end: postcode -> gov data -> filtered stations.
    # NOTE: slow — this loads the entire forecourt dataset on first call.
    from fuel_finder_client.fuel_finder_client import FuelFinderClient

    client = FuelFinderClient()
    try:
        stations = await client.get("CM2 9JT", 10)
        assert isinstance(stations, list)
    finally:
        await client.aclose()
