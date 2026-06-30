from asyncio import create_task
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from fuel_finder_client.fuel_finder_client import (
    FuelFinderClient,
    PostcodeError,
    Sort,
    Station,
)
from gov_api_client.gov_client import GovApiError
from gov_api_client.models import FuelType
from logging_config import configure_logging

configure_logging()

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Human-readable labels for the UI dropdowns — kept in the app layer, not the
# data models.
_FUEL_TYPE_LABELS = {
    FuelType.UNLEADED: "Unleaded (E10)",
    FuelType.SUPER_UNLEADED: "Super Unleaded (E5)",
    FuelType.DIESEL: "Diesel (B7)",
    FuelType.PREMIUM_DIESEL: "Premium Diesel (B7)",
    FuelType.DIESEL_B10: "Diesel (B10)",
    FuelType.HVO: "HVO — Renewable Diesel",
}
_SORT_LABELS = {Sort.CHEAPEST: "Cheapest first", Sort.DISTANCE: "Nearest first"}


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


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    postcode: str | None = None,
    max_distance_miles: int = 10,
    fuel_type: FuelType = FuelType.UNLEADED,
    sort: Sort = Sort.CHEAPEST,
) -> HTMLResponse:
    found: list[Station] | None = None
    error: str | None = None
    if postcode:
        try:
            found = await fuel_finder_client.get(
                postcode, max_distance_miles, fuel_type, sort
            )
        except PostcodeError:
            error = f"Couldn't find postcode '{postcode}'."
        except GovApiError:
            error = "Fuel data is temporarily unavailable — please try again."

    context: dict[str, Any] = {
        "stations": found,
        "error": error,
        "fuel_types": [(ft.value, _FUEL_TYPE_LABELS[ft]) for ft in FuelType],
        "sorts": [(s.value, _SORT_LABELS[s]) for s in Sort],
        "postcode": postcode or "",
        "max_distance_miles": max_distance_miles,
        "selected_fuel_type": fuel_type.value,
        "selected_sort": sort.value,
    }
    # HTMX request -> return just the results fragment; full page otherwise.
    name = "_stations.html" if request.headers.get("HX-Request") else "index.html"
    return templates.TemplateResponse(request, name, context)
