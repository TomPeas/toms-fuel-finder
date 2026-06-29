"""Shared fixtures: ready-built model instances + integration credentials."""

import os
from datetime import datetime, time

import pytest

from gov_api_client.models import (
    BankHoliday,
    DayOpening,
    ForecourtInfo,
    ForecourtPrices,
    FuelPrice,
    FuelType,
    Location,
    OpeningTimes,
    UsualDays,
)

_TS = datetime(2026, 2, 17, 16, 0, 0)

_REQUIRED_ENV = ("GOV_CLIENT_ID", "GOV_CLIENT_SECRET", "GOV_BASE_URL")


@pytest.fixture
def gov_credentials() -> dict[str, str]:
    """Real gov credentials from the environment, for integration tests.

    Skips (rather than fails) when the env vars are absent, so unit runs and CI
    without secrets are unaffected.
    """
    missing = [name for name in _REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        pytest.skip(f"set {', '.join(_REQUIRED_ENV)} to run integration tests")
    return {
        "client_id": os.environ["GOV_CLIENT_ID"],
        "client_secret": os.environ["GOV_CLIENT_SECRET"],
        "base_url": os.environ["GOV_BASE_URL"],
    }


def _day() -> DayOpening:
    return DayOpening(open=time(6, 0), close=time(22, 0), is_24_hours=False)


@pytest.fixture
def sample_info() -> ForecourtInfo:
    return ForecourtInfo(
        node_id="n1",
        trading_name="Station One",
        brand_name="BrandCo",
        is_same_trading_and_brand_name=True,
        temporary_closure=False,
        is_motorway_service_station=False,
        is_supermarket_service_station=False,
        location=Location(
            address_line_1="1 Road",
            city="Townsville",
            country="England",
            postcode="AB1 2CD",
            latitude=51.5,
            longitude=-0.1,
        ),
        amenities=["car_wash"],
        opening_times=OpeningTimes(
            usual_days=UsualDays(
                monday=_day(),
                tuesday=_day(),
                wednesday=_day(),
                thursday=_day(),
                friday=_day(),
                saturday=_day(),
                sunday=_day(),
            ),
            bank_holiday=BankHoliday(
                type="standard",
                open_time=time(8, 0),
                close_time=time(20, 0),
                is_24_hours=False,
            ),
        ),
        fuel_types=[FuelType.UNLEADED, FuelType.DIESEL],
    )


@pytest.fixture
def sample_price() -> FuelPrice:
    return FuelPrice(
        fuel_type=FuelType.UNLEADED,
        price=132.9,
        price_last_updated=_TS,
        price_change_effective_timestamp=_TS,
    )


@pytest.fixture
def sample_prices(sample_price: FuelPrice) -> ForecourtPrices:
    return ForecourtPrices(
        node_id="n1",
        trading_name="Station One",
        fuel_prices=[sample_price],
    )
