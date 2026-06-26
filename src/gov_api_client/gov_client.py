from asyncio import gather

from cachetools import TTLCache
from httpx import AsyncClient

from gov_api_client.auth.bearer_auth import BearerAuth
from gov_api_client.auth_client import AuthClient
from gov_api_client.models import Forecourt, FuelPricesResponse, PFSInfoResponse


class GovClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self._base_url = base_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._auth_client = AuthClient(client_id, client_secret, base_url)
        self._http_client = AsyncClient(
            base_url=self._base_url, auth=BearerAuth(self._auth_client)
        )
        self.forecourts: TTLCache[str, dict[str, Forecourt]] = TTLCache(
            maxsize=1, ttl=3500
        )

    async def get_forecourt_data(self, ids: list[str] | None) -> dict[str, Forecourt]:
        if len(self.forecourts) == 0:
            await self.update()
        if ids is None:
            return self.forecourts["data"]
        res: dict[str, Forecourt] = {}
        for forecourt_id in ids:
            res[forecourt_id] = self.forecourts["data"][forecourt_id]
        return res

    async def update(self) -> None:
        pfs_info, fuel_price_info = await gather(
            self._fetch_all_pfs_information(),
            self._fetch_all_fuel_prices(),
        )
        forecourts: dict[str, Forecourt] = {}
        for pfs in pfs_info.data:
            forecourts[pfs.node_id] = Forecourt(
                node_id=pfs.node_id,
                trading_name=pfs.trading_name,
                postcode=pfs.location.postcode,
                latitude=pfs.location.latitude,
                longitude=pfs.location.longitude,
                prices=[],
            )

        for price in fuel_price_info.data:
            forecourts[price.node_id].prices = price.fuel_prices
        self.forecourts["data"] = forecourts

    async def _fetch_all_fuel_prices(self) -> FuelPricesResponse:
        batch_number = 1
        prices = FuelPricesResponse(data=[])
        while True:
            res = await self._fetch_fuel_price(batch_number)
            if len(res.data) == 0:
                break
            prices = FuelPricesResponse(data=prices.data + res.data)
            batch_number += 1
        return prices

    async def _fetch_fuel_price(self, batch_number: int) -> FuelPricesResponse:
        response = await self._http_client.get(
            f"/api/v1/pfs/fuel-prices?batch-number={batch_number}"
        )
        if response.status_code == 404:
            return FuelPricesResponse(data=[])
        response.raise_for_status()
        res = response.json()
        return FuelPricesResponse(data=res)

    async def _fetch_all_pfs_information(self) -> PFSInfoResponse:
        batch_number = 1
        info = PFSInfoResponse(data=[])
        while True:
            res = await self._fetch_pfs_information(batch_number)
            if len(res.data) == 0:
                break
            info = PFSInfoResponse(data=info.data + res.data)
            batch_number += 1
        return info

    async def _fetch_pfs_information(self, batch_number: int) -> PFSInfoResponse:
        response = await self._http_client.get(
            f"/api/v1/pfs?batch-number={batch_number}"
        )
        if response.status_code == 404:
            return PFSInfoResponse(data=[])
        response.raise_for_status()
        res = response.json()
        return PFSInfoResponse(data=res)

    async def close(self) -> None:
        await self._auth_client.aclose()
        await self._http_client.aclose()
