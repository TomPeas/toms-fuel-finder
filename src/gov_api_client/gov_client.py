from asyncio import Lock, Semaphore, gather, sleep
from datetime import UTC, datetime

from httpx import AsyncClient, HTTPStatusError, Limits, RequestError, Response

from gov_api_client.auth.bearer_auth import BearerAuth
from gov_api_client.auth_client import AuthClient
from gov_api_client.models import Forecourt, FuelPricesResponse, PFSInfoResponse
from logging_config import HTTPX_EVENT_HOOKS, logger


class GovApiError(Exception):
    """Raised when a Fuel Finder data request fails (bad status or unreachable).

    The HTTP error itself is logged at WARNING by the client's response hook;
    this carries a clean message up to the caller.
    """


# Statuses worth retrying — the gov service intermittently returns these.
_TRANSIENT_STATUS = frozenset({429, 502, 503, 504})
_MAX_ATTEMPTS = 4


def _is_transient(exc: RequestError | HTTPStatusError) -> bool:
    """A network error, or one of the retryable 'try again' statuses."""
    if isinstance(exc, HTTPStatusError):
        return exc.response.status_code in _TRANSIENT_STATUS
    return True  # RequestError = connect/read/timeout — always worth a retry


class GovClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self._base_url = base_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._auth_client = AuthClient(client_id, client_secret, base_url)
        self.forecourts: dict[str, Forecourt] = {}
        self._last_update: datetime | None = None
        self._UPDATE_INTERVAL_SECONDS = 30 * 60
        self._MAX_BATCH_SIZE = 3
        self._semaphore = Semaphore(self._MAX_BATCH_SIZE)
        self._http_connection_limit = Limits(max_connections=100)
        self._http_client = AsyncClient(
            base_url=self._base_url,
            auth=BearerAuth(self._auth_client),
            http2=True,
            limits=self._http_connection_limit,
            event_hooks=HTTPX_EVENT_HOOKS,
        )
        self._mutex = Lock()

    async def get_forecourt_data(self, ids: list[str] | None) -> dict[str, Forecourt]:
        now = datetime.now(UTC)
        is_first_run = self._last_update is None and len(self.forecourts) == 0
        has_expired = (
            (now - self._last_update).total_seconds() > self._UPDATE_INTERVAL_SECONDS
            if self._last_update
            else False
        )
        if not is_first_run and not has_expired:
            logger.debug("returning cached forecourt data")
            return self._get_forecourts(ids)

        async with self._mutex:
            if is_first_run:
                await self._collect()
                self._last_update = now
            elif has_expired:
                await self._collect(
                    self._last_update.isoformat() if self._last_update else None
                )
                self._last_update = now
            return self._get_forecourts(ids)

    def _get_forecourts(self, ids: list[str] | None) -> dict[str, Forecourt]:
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

    async def _get(self, url: str, params: dict[str, str | int]) -> Response:
        """GET with retry + exponential backoff on transient errors. Returns the
        response (caller handles 404); re-raises the underlying httpx error once
        retries are exhausted or the error is permanent (e.g. 403)."""
        delay = 0.5
        for attempt in range(_MAX_ATTEMPTS):
            try:
                async with self._semaphore:
                    response = await self._http_client.get(url, params=params)
                if response.status_code != 404:
                    response.raise_for_status()
                return response
            except (RequestError, HTTPStatusError) as e:
                if not _is_transient(e) or attempt == _MAX_ATTEMPTS - 1:
                    raise
                logger.warning(
                    "transient error on %s (attempt %d/%d) — retrying in %.1fs",
                    url,
                    attempt + 1,
                    _MAX_ATTEMPTS,
                    delay,
                )
                await sleep(delay)
                delay *= 2
        raise AssertionError("unreachable")  # loop always returns or raises

    async def _fetch_fuel_price(
        self, batch_number: int, iso_timestamp: str | None = None
    ) -> FuelPricesResponse:
        params: dict[str, str | int] = {
            "batch-number": batch_number,
            **({"effective-start-timestamp": iso_timestamp} if iso_timestamp else {}),
        }
        try:
            response = await self._get("/api/v1/pfs/fuel-prices", params)
        except HTTPStatusError as e:
            raise GovApiError(
                f"Fuel prices request failed: HTTP {e.response.status_code}"
            ) from e
        except RequestError as e:
            raise GovApiError("Could not reach the Fuel Finder service.") from e
        if response.status_code == 404:
            return FuelPricesResponse(data=[])
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
        params: dict[str, str | int] = {
            "batch-number": batch_number,
            **({"effective-start-timestamp": iso_timestamp} if iso_timestamp else {}),
        }
        try:
            response = await self._get("/api/v1/pfs", params)
        except HTTPStatusError as e:
            raise GovApiError(
                f"PFS info request failed: HTTP {e.response.status_code}"
            ) from e
        except RequestError as e:
            raise GovApiError("Could not reach the Fuel Finder service.") from e
        if response.status_code == 404:
            return PFSInfoResponse(data=[])
        return PFSInfoResponse(data=response.json())

    async def aclose(self) -> None:
        await self._auth_client.aclose()
        await self._http_client.aclose()
