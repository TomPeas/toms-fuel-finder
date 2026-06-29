from enum import StrEnum
from operator import attrgetter

from haversine import Unit, haversine
from httpx import Client
from pydantic import BaseModel

from config import settings
from gov_api_client.gov_client import GovClient
from gov_api_client.models import Forecourt, FuelType


class Sort(StrEnum):
    DISTANCE = "distance"
    CHEAPEST = "cheapest"


class Station(BaseModel):
    name: str
    postcode: str
    distance_miles: int
    fuel_type: FuelType
    price_per_liter: float | None


class FuelFinderClient:
    def __init__(self) -> None:
        self._gov_client = GovClient(
            settings.gov_base_url, settings.gov_client_id, settings.gov_client_secret
        )
        self._post_code_client = Client(base_url="https://api.postcodes.io")

    def _get_coords(self, postcode: str) -> tuple[int, int]:
        response = self._post_code_client.get(f"/postcodes/{postcode}")
        response.raise_for_status()
        data = response.json()
        return data["result"]["latitude"], data["result"]["longitude"]

    async def _get_forecourts(self) -> dict[str, Forecourt]:
        return await self._gov_client.get_forecourt_data(None)

    async def get(
        self,
        postcode: str,
        max_distance_miles: int = 10,
        fuel_type: FuelType = FuelType.UNLEADED,
        sort: Sort = Sort.CHEAPEST,
    ) -> list[Station]:
        centre = self._get_coords(postcode)
        forecourts = await self._get_forecourts()
        res: list[Station] = []
        for fc in forecourts.values():
            distance = haversine(centre, (fc.latitude, fc.longitude), unit=Unit.MILES)
            if distance <= max_distance_miles:
                station = Station(
                    name=fc.trading_name,
                    postcode=fc.postcode,
                    distance_miles=round(distance),
                    fuel_type=fuel_type,
                    price_per_liter=next(
                        (p.price for p in fc.prices if p.fuel_type == fuel_type), None
                    ),
                )
                res.append(station) if station.price_per_liter is not None else None
        keys = {
            Sort.CHEAPEST: attrgetter("price_per_liter"),
            Sort.DISTANCE: attrgetter("distance_miles"),
        }
        res.sort(key=keys[sort])
        return res
