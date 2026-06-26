"""Shared fixtures: ready-built model instances for the unit tests."""

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
