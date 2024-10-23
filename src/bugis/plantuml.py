from typing import TYPE_CHECKING

from aiofiles import open as async_open
from aiohttp import ClientSession
from .configuration import Configuration
from yarl import URL
if TYPE_CHECKING:
    from _typeshed import StrOrBytesPath

async def render_plant_uml(path: 'StrOrBytesPath') -> bytes:
    async with ClientSession() as session:
        url = URL(Configuration.instance.plant_uml_server_address) / 'svg'
        async with async_open(path, 'rb') as file:
            source = await file.read()
            async with session.post(url, data=source) as response:
                response.raise_for_status()
                return await response.read()
