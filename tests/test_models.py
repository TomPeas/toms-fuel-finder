"""Unit tests for the Pydantic models. No external dependencies to mock."""

from gov_api_client.models import (
    ForecourtInfo,
    ForecourtPrices,
    FuelPricesResponse,
    FuelType,
    PFSInfoResponse,
)


def test_fueltype_names_map_to_wire_codes() -> None:
    assert FuelType.UNLEADED.value == "E10"
    assert FuelType.SUPER_UNLEADED.value == "E5"
    assert FuelType.DIESEL.value == "B7_STANDARD"
    assert FuelType.PREMIUM_DIESEL.value == "B7_PREMIUM"


def test_fueltype_parses_from_wire_code() -> None:
    assert FuelType("E5") is FuelType.SUPER_UNLEADED


def test_fuel_prices_response_round_trips(sample_prices: ForecourtPrices) -> None:
    payload = FuelPricesResponse(data=[sample_prices]).model_dump(mode="json")
    parsed = FuelPricesResponse.model_validate(payload)

    price = parsed.data[0].fuel_prices[0]
    assert price.fuel_type is FuelType.UNLEADED
    assert price.price == 132.9


def test_pfs_info_response_round_trips(sample_info: ForecourtInfo) -> None:
    payload = PFSInfoResponse(data=[sample_info]).model_dump(mode="json")
    parsed = PFSInfoResponse.model_validate(payload)

    forecourt = parsed.data[0]
    assert forecourt.node_id == "n1"
    assert forecourt.location.postcode == "AB1 2CD"
    # optional field absent in the fixture -> defaults to None
    assert forecourt.public_phone_number is None
