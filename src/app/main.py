from asyncio import create_task
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import Enum

from fastapi import FastAPI, Response, status
from pydantic import BaseModel

from fuel_finder_client.fuel_finder_client import FuelFinderClient, Sort, Station
from gov_api_client.models import FuelType
from logging_config import configure_logging

configure_logging()


class FuelFinderResponse(BaseModel):
    stations: list[Station]


class HealthStatus(Enum):
    OK = "ok"
    ERROR = "error"


class HealthResponse(BaseModel):
    status: HealthStatus


fuel_finder_client = FuelFinderClient()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Warm the cache in the background so startup (and /livez) isn't blocked.
    warm_task = create_task(
        fuel_finder_client.get("SW1A 1AA", 10, FuelType.UNLEADED, Sort.CHEAPEST)
    )
    yield
    warm_task.cancel()
    await fuel_finder_client.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/readyz")
async def readyz(response: Response) -> HealthResponse:
    if fuel_finder_client.is_ready():  # cache populated?
        return HealthResponse(status=HealthStatus.OK)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status=HealthStatus.ERROR)


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
    res = await fuel_finder_client.get(postcode, max_distance_miles, fuel_type, sort)
    return FuelFinderResponse(stations=res)
