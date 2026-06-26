"""Pydantic models for the Fuel Finder (Information Recipient) API.

Hand-written from the OpenAPI spec, with field types corrected to match the
real example payloads rather than the spec's declared types (the spec declares
`price` as a string and `public_phone_number` as a number, but the examples show
a number and a nullable string respectively).
"""

from datetime import date, datetime, time
from enum import StrEnum

from pydantic import BaseModel


class FuelType(StrEnum):
    """Fuel grades.

    Member names are human-readable; the values are the codes the API actually
    uses on the wire. Pydantic validates/serialises by value, so referring to
    `FuelType.SUPER_UNLEADED` in code is purely a readability win — the data
    model still sends and receives `"E5"` etc. unchanged.
    """

    UNLEADED = "E10"  # standard unleaded petrol (up to 10% ethanol)
    SUPER_UNLEADED = "E5"  # premium unleaded petrol (up to 5% ethanol)
    DIESEL = "B7_STANDARD"  # standard diesel (up to 7% biodiesel)
    PREMIUM_DIESEL = "B7_PREMIUM"  # premium diesel
    DIESEL_B10 = "B10"  # diesel with up to 10% biodiesel
    HVO = "HVO"  # hydrotreated vegetable oil (renewable diesel)


# ── Fuel prices endpoints ──────────────────────────────────────────────
# GET /api/v1/pfs/fuel-prices (and the incremental variant)


class FuelPrice(BaseModel):
    fuel_type: FuelType
    price: float  # pence per litre, e.g. 159.9 (spec says string — it's a number)
    price_last_updated: datetime
    price_change_effective_timestamp: datetime


class ForecourtPrices(BaseModel):
    node_id: str
    public_phone_number: str | None = None  # null / "" / "+44..." in examples
    trading_name: str
    fuel_prices: list[FuelPrice]


class FuelPricesResponse(BaseModel):
    """Top-level response: a `data` array of forecourts with their prices."""

    data: list[ForecourtPrices]


# ── PFS information endpoints ───────────────────────────────────────────
# GET /api/v1/pfs (and the incremental variant)


class Location(BaseModel):
    address_line_1: str
    address_line_2: str | None = None
    city: str
    country: str | None = None
    county: str | None = None
    postcode: str
    latitude: float
    longitude: float


class DayOpening(BaseModel):
    open: time | None = None  # "06:00:00", or null when hours are unset
    close: time | None = None
    is_24_hours: bool


class BankHoliday(BaseModel):
    type: str
    open_time: time | None = None
    close_time: time | None = None
    is_24_hours: bool


class UsualDays(BaseModel):
    monday: DayOpening
    tuesday: DayOpening
    wednesday: DayOpening
    thursday: DayOpening
    friday: DayOpening
    saturday: DayOpening
    sunday: DayOpening


class OpeningTimes(BaseModel):
    usual_days: UsualDays
    bank_holiday: BankHoliday | None = None  # note: singular in this API


class ForecourtInfo(BaseModel):
    node_id: str
    public_phone_number: str | None = None
    trading_name: str
    is_same_trading_and_brand_name: bool
    brand_name: str
    temporary_closure: bool
    permanent_closure: bool | None = None
    permanent_closure_date: date | None = None
    is_motorway_service_station: bool
    is_supermarket_service_station: bool
    location: Location
    amenities: list[str]  # e.g. ["adblue_pumps", "car_wash"] — empty list if none
    opening_times: OpeningTimes
    fuel_types: list[FuelType]  # e.g. ["E10", "E5", "HVO"]


class PFSInfoResponse(BaseModel):
    """Top-level response: a `data` array of forecourts (up to 500 per batch)."""

    data: list[ForecourtInfo]


class Forecourt(BaseModel):
    node_id: str
    trading_name: str
    postcode: str
    latitude: float
    longitude: float
    prices: list[FuelPrice]
