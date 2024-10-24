from typing import TYPE_CHECKING

from aiofiles import open as async_open
from .configuration import Configuration
if TYPE_CHECKING:
    from _typeshed import StrOrBytesPath
from httpx import AsyncClient, URL
from typing import Callable, Awaitable
from urllib.parse import urljoin

chunk_size = 0x10000
async def render_plant_uml(client: AsyncClient, path: 'StrOrBytesPath', send : Callable[[bytes], Awaitable[None]]):
    url = URL(urljoin(Configuration.instance.plant_uml_server_address, 'svg'))
    async with async_open(path, 'rb') as file:
        source = await file.read()
        response = await client.post(url, content=source)
        response.raise_for_status()
        async for chunk in response.aiter_bytes(chunk_size=chunk_size):
            await send(chunk)
