from enum import Enum

from fastapi import FastAPI
from pydantic import BaseModel

from fuel_finder_client.fuel_finder_client import FuelFinderClient, Sort, Station
from gov_api_client.models import FuelType


class FuelFinderResponse(BaseModel):
    stations: list[Station]


class HealthStatus(Enum):
    OK = "ok"
    ERROR = "error"


class HealthResponse(BaseModel):
    status: HealthStatus


app = FastAPI()
fuel_finder_client = FuelFinderClient()


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status=HealthStatus.OK)


@app.get("/stations")
async def stations(
    postcode: str,
    max_distance_miles: int = 10,
    fuel_type: FuelType = FuelType.UNLEADED,
    sort: Sort = Sort.CHEAPEST,
) -> FuelFinderResponse:
    return FuelFinderResponse(
        stations=await fuel_finder_client.get(
            postcode, max_distance_miles, fuel_type, sort
        )
    )
