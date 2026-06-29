from asyncio import Semaphore, gather
from datetime import UTC, datetime

from httpx import AsyncClient, HTTPStatusError, Limits, RequestError

from gov_api_client.auth.bearer_auth import BearerAuth
from gov_api_client.auth_client import AuthClient
from gov_api_client.models import Forecourt, FuelPricesResponse, PFSInfoResponse
from logging_config import HTTPX_EVENT_HOOKS, logger


class GovApiError(Exception):
    """Raised when a Fuel Finder data request fails (bad status or unreachable).

    The HTTP error itself is logged at WARNING by the client's response hook;
    this carries a clean message up to the caller.
    """


class GovClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self._base_url = base_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._auth_client = AuthClient(client_id, client_secret, base_url)
        self.forecourts: dict[str, Forecourt] = {}
        self._last_update: datetime | None = None
        self._UPDATE_INTERVAL_SECONDS = 30 * 60
        self._MAX_BATCH_SIZE = 6
        self._semaphore = Semaphore(self._MAX_BATCH_SIZE)
        self._http_connection_limit = Limits(max_connections=100)
        self._http_client = AsyncClient(
            base_url=self._base_url,
            auth=BearerAuth(self._auth_client),
            http2=True,
            limits=self._http_connection_limit,
            event_hooks=HTTPX_EVENT_HOOKS,
        )

    async def get_forecourt_data(self, ids: list[str] | None) -> dict[str, Forecourt]:
        now = datetime.now(UTC)
        if self._last_update is None or len(self.forecourts) == 0:
            self._last_update = now
            await self._collect()
        elif (now - self._last_update).total_seconds() > self._UPDATE_INTERVAL_SECONDS:
            await self._collect(self._last_update.isoformat())
            self._last_update = now
        if ids is None:
            return self.forecourts
        res: dict[str, Forecourt] = {}
        for forecourt_id in ids:
            res[forecourt_id] = self.forecourts[forecourt_id]
        return res

    async def _collect(self, timestamp: str | None = None) -> None:
        pfs_info, fuel_price_info = await gather(
            self._fetch_all_pfs_information(timestamp),
            self._fetch_all_fuel_prices(timestamp),
        )
        for pfs in pfs_info.data:
            self.forecourts[pfs.node_id] = Forecourt(
                node_id=pfs.node_id,
                trading_name=pfs.trading_name,
                postcode=pfs.location.postcode,
                latitude=pfs.location.latitude,
                longitude=pfs.location.longitude,
                prices=[],
            )

        for price in fuel_price_info.data:
            self.forecourts[price.node_id].prices = price.fuel_prices

    async def _fetch_all_fuel_prices(
        self, timestamp: str | None = None
    ) -> FuelPricesResponse:
        batch_number = 1
        prices = FuelPricesResponse(data=[])
        end = False
        while not end:
            logger.debug(
                "fetching price batches %d-%d",
                batch_number,
                batch_number + self._MAX_BATCH_SIZE - 1,
            )
            batch_requests = [
                self._fetch_fuel_price(i, iso_timestamp=timestamp)
                for i in range(batch_number, batch_number + self._MAX_BATCH_SIZE)
            ]
            res = await gather(*batch_requests)
            for r in res:
                if len(r.data) == 0:
                    end = True
                else:
                    prices = FuelPricesResponse(data=prices.data + r.data)
            batch_number += self._MAX_BATCH_SIZE  # ← once per wave
        return prices

    async def _fetch_fuel_price(
        self, batch_number: int, iso_timestamp: str | None = None
    ) -> FuelPricesResponse:
        async with self._semaphore:
            params: dict[str, str | int] = {
                "batch-number": batch_number,
                **(
                    {"effective-start-timestamp": iso_timestamp}
                    if iso_timestamp
                    else {}
                ),
            }
            try:
                response = await self._http_client.get(
                    "/api/v1/pfs/fuel-prices",
                    params=params,
                )
                if response.status_code == 404:
                    return FuelPricesResponse(data=[])
                response.raise_for_status()
            except HTTPStatusError as e:
                raise GovApiError(
                    f"Fuel prices request failed: HTTP {e.response.status_code}"
                ) from e
            except RequestError as e:
                raise GovApiError("Could not reach the Fuel Finder service.") from e
            return FuelPricesResponse(data=response.json())

    async def _fetch_all_pfs_information(
        self, timestamp: str | None = None
    ) -> PFSInfoResponse:
        batch_number = 1
        info = PFSInfoResponse(data=[])
        end = False
        while not end:
            logger.debug(
                "fetching info batches %d-%d",
                batch_number,
                batch_number + self._MAX_BATCH_SIZE - 1,
            )
            batch_requests = [
                self._fetch_pfs_information(i, iso_timestamp=timestamp)
                for i in range(batch_number, batch_number + self._MAX_BATCH_SIZE)
            ]
            res = await gather(*batch_requests)
            for r in res:
                if len(r.data) == 0:
                    end = True
                else:
                    info = PFSInfoResponse(data=info.data + r.data)
            batch_number += self._MAX_BATCH_SIZE  # ← once per wave
        return info

    async def _fetch_pfs_information(
        self, batch_number: int, iso_timestamp: str | None = None
    ) -> PFSInfoResponse:
        async with self._semaphore:
            params: dict[str, str | int] = {
                "batch-number": batch_number,
                **(
                    {"effective-start-timestamp": iso_timestamp}
                    if iso_timestamp
                    else {}
                ),
            }
            try:
                response = await self._http_client.get("/api/v1/pfs", params=params)
                if response.status_code == 404:
                    return PFSInfoResponse(data=[])
                response.raise_for_status()
            except HTTPStatusError as e:
                raise GovApiError(
                    f"PFS info request failed: HTTP {e.response.status_code}"
                ) from e
            except RequestError as e:
                raise GovApiError("Could not reach the Fuel Finder service.") from e
            return PFSInfoResponse(data=response.json())

    async def close(self) -> None:
        await self._auth_client.aclose()
        await self._http_client.aclose()
