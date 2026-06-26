import asyncio

from pydantic import TypeAdapter

from fuel_finder_client.fuel_finder_client import FuelFinderClient, Station


async def test() -> None:
    res = await FuelFinderClient().get("CM29JT", 10)
    print(TypeAdapter(list[Station]).dump_json(res, indent=2).decode())


if __name__ == "__main__":
    asyncio.run(test())
