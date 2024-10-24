import hashlib
import logging
from asyncio import AbstractEventLoop
from asyncio import Future
from io import BytesIO
from mimetypes import init as mimeinit, guess_type
from os import getcwd
from os.path import join, normpath, splitext, relpath, basename
from typing import Callable, TYPE_CHECKING, Optional, Awaitable, AsyncGenerator, Any, Mapping

import pygraphviz as pgv
from aiofiles import open as async_open
from aiofiles.base import AiofilesContextManager
from aiofiles.os import listdir
from aiofiles.ospath import exists, isdir, isfile, getmtime
from aiofiles.threadpool.binary import AsyncBufferedReader
from httpx import AsyncClient
from pwo import Maybe

from .asgi_utils import encode_headers
from .async_watchdog import FileWatcher
from .md2html import compile_html, load_from_cache, STATIC_RESOURCES, MARDOWN_EXTENSIONS
from .plantuml import render_plant_uml

if TYPE_CHECKING:
    from _typeshed import StrOrBytesPath

mimeinit()

cwd: 'StrOrBytesPath' = getcwd()


def completed_future[T](result: T) -> Future[T]:
    future = Future()
    future.set_result(result)
    return future


def has_extension(filepath, extension):
    _, ext = splitext(filepath)
    return ext == extension


def is_markdown(filepath):
    return has_extension(filepath, ".md")


def is_dotfile(filepath):
    return has_extension(filepath, ".dot")


def is_plant_uml(filepath):
    return has_extension(filepath, ".puml")


logger = logging.getLogger(__name__)


class Server:
    root_dir: 'StrOrBytesPath'
    prefix: Optional['StrOrBytesPath']
    _loop: AbstractEventLoop
    _client: AsyncClient

    def __init__(self,
                 root_dir: 'StrOrBytesPath' = getcwd(),
                 prefix: Optional['StrOrBytesPath'] = None,
                 loop: AbstractEventLoop = None):
        self.root_dir = root_dir
        self.cache = dict['StrOrBytesPath', tuple[str, float]]()
        self.file_watcher = FileWatcher(cwd)
        self.prefix = prefix and normpath(f'{prefix.decode()}')
        self._loop = loop
        self._client = AsyncClient()

    async def handle_request(self,
            method: str,
            url_path: str,
            etag: Optional[str],
            query_string: Optional[str],
            send: Callable[[Mapping[str, Any]], Awaitable[None]],
            pathsend: bool = False
         ):
        if method != 'GET':
            await send({
                'type': 'http.response.start',
                'status': 405
            })
            await send({
                'type': 'http.response.body',
                'body': b'',
            })
            return
        relative_path = relpath(url_path, start=self.prefix or '/')
        url_path: 'StrOrBytesPath' = normpath(join('/', relative_path))
        path: 'StrOrBytesPath' = join(self.root_dir, relative_path)
        if url_path in STATIC_RESOURCES:
            content, mtime = await load_from_cache(url_path)
            content = content.encode()
            etag, digest = await self.compute_etag_and_digest(
                etag,
                url_path,
                lambda: AiofilesContextManager(
                    completed_future(AsyncBufferedReader(BytesIO(content), loop=self._loop, executor=None))),
                lambda: completed_future(mtime)
            )
            if etag and etag == digest:
                await self.not_modified(send, digest, 'must-revalidate, max-age=86400')
                return
            elif content:
                mime_type = guess_type(basename(url_path))[0] or 'application/octet-stream'
                await send({
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': encode_headers({
                        'content-type': f'{mime_type}; charset=UTF-8',
                        'etag': f'W/{digest}',
                        'Cache-Control': 'must-revalidate, max-age=86400',
                    })
                })
                await send({
                    'type': 'http.response.body',
                    'body': content
                })
                return
        elif await exists(path):
            if await isfile(path):
                etag, digest = await self.compute_etag_and_digest(
                    etag,
                    path,
                    lambda: async_open(path, 'rb'),
                    lambda: getmtime(path)
                )
                logger.debug('Etag: %s, digest: %s', etag, digest)
                if etag and etag == digest:
                    if is_markdown(path) and query_string == 'reload':
                        subscription = self.file_watcher.subscribe(path)
                        try:
                            has_changed = await subscription.wait(30)
                            if has_changed:
                                _, digest = await self.compute_etag_and_digest(
                                    etag,
                                    path,
                                    lambda: async_open(path, 'rb'),
                                    lambda: getmtime(path)
                                )
                                if etag != digest:
                                    if await exists(path) and await isfile(path):
                                        await self.render_markdown(url_path, path, True, digest, send)
                                        return
                                    else:
                                        await self.not_found(send)
                                        return
                        finally:
                            subscription.unsubscribe()
                    await self.not_modified(send, digest)
                elif is_markdown(path):
                    raw = query_string == 'reload'
                    await self.render_markdown(url_path, path, raw, digest, send)
                elif is_dotfile(path):
                    def render_graphviz(filepath: StrOrBytesPath) -> bytes:
                        logger.debug("Starting Graphviz rendering for file '%s'", filepath)
                        graph = pgv.AGraph(filepath)
                        result = graph.draw(None, format="svg", prog="dot")
                        logger.debug("Completed Graphviz rendering for file '%s'", filepath)
                        return result

                    body = await self._loop.run_in_executor(None, render_graphviz, path)
                    await send({
                        'type': 'http.response.start',
                        'status': 200,
                        'headers': encode_headers({
                            'Content-Type': 'image/svg+xml; charset=UTF-8',
                            'Etag': f'W/{digest}',
                            'Cache-Control': 'no-cache',
                        })
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': body
                    })
                elif is_plant_uml(path):
                    logger.debug("Starting PlantUML rendering for file '%s'", path)
                    logger.debug("Completed PlantUML rendering for file '%s'", path)
                    await send({
                        'type': 'http.response.start',
                        'status': 200,
                        'headers': encode_headers({
                            'Content-Type': 'image/svg+xml; charset=UTF-8',
                            'Etag': f'W/{digest}',
                            'Cache-Control': 'no-cache'
                        })
                    })
                    await render_plant_uml(self._client, path, lambda chunk: send({
                        'type': 'http.response.body',
                        'body': chunk,
                        'more_body': True
                    }))
                    await send({
                        'type': 'http.response.body',
                        'body': '',
                        'more_body': False
                    })
                else:
                    async def read_file(file_path, buffer_size=0x10000):
                        async with async_open(file_path, 'rb') as f:
                            while True:
                                result = await f.read(buffer_size)
                                if len(result) == 0:
                                    break
                                yield result

                    await send({
                        'type': 'http.response.start',
                        'status': 200,
                        'headers': encode_headers({
                            'Content-Type': guess_type(basename(path))[0] or 'application/octet-stream',
                            'Etag': f'W/{digest}',
                            'Cache-Control': 'no-cache'
                        })
                    })
                    if pathsend:
                        await send({
                            'type': 'http.response.pathsend',
                            'path': path
                        })
                    else:
                        async for chunk in read_file(path):
                            await send({
                                'type': 'http.response.body',
                                'body': chunk,
                                'more_body': True
                            })
                        await send({
                            'type': 'http.response.body',
                            'body': b'',
                            'more_body': False
                        })

            elif await isdir(path):
                body = (await self.directory_listing(url_path, path)).encode()
                await send({
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': encode_headers({
                        'Content-Type': 'text/html; charset=UTF-8',
                    })
                })
                await send({
                    'type': 'http.response.body',
                    'body': body
                })
        else:
            await self.not_found(send)

    @staticmethod
    async def stream_hash(source: AsyncBufferedReader, bufsize=0x10000) -> bytes:
        if bufsize <= 0:
            raise ValueError("Buffer size must be greater than 0")
        md5 = hashlib.md5()
        while True:
            buf = await source.read(bufsize)
            if len(buf) == 0:
                break
            md5.update(buf)
        return md5.digest()

    @staticmethod
    async def file_hash(filepath, bufsize=0x10000) -> bytes:
        if bufsize <= 0:
            raise ValueError("Buffer size must be greater than 0")
        md5 = hashlib.md5()
        async with async_open(filepath, 'rb') as f:
            while True:
                buf = await f.read(bufsize)
                if len(buf) == 0:
                    break
                md5.update(buf)
        return md5.digest()

    @staticmethod
    def parse_etag(etag: str) -> Optional[str]:
        def skip_weak_marker(s):
            if s.startswith('W/'):
                return s[2:]
            else:
                return s

        return (
            Maybe.of_nullable(etag)
            .map(skip_weak_marker)
            .or_else(None)
        )

    async def compute_etag_and_digest(
            self,
            etag_header: str,
            path: str,
            stream_source: Callable[[], AiofilesContextManager[AsyncBufferedReader]],
            mtime_supplier: Callable[[], Awaitable[float]]
    ) -> tuple[str, str]:
        cache_result = self.cache.get(path)
        _mtime: Optional[float] = None

        async def mtime() -> float:
            nonlocal _mtime
            if not _mtime:
                _mtime = await mtime_supplier()
            return _mtime

        if not cache_result or cache_result[1] < await mtime():
            async with stream_source() as stream:
                digest = (await Server.stream_hash(stream)).hex()
            self.cache[path] = digest, await mtime()
        else:
            digest = cache_result[0]

        etag = Server.parse_etag(etag_header)
        return etag, digest

    async def render_markdown(self,
                              url_path: 'StrOrBytesPath',
                              path: str,
                              raw: bool,
                              digest: str,
                              send) -> None:

        body = await compile_html(
            url_path,
            path,
            self._loop,
            self.prefix,
            MARDOWN_EXTENSIONS,
            raw=raw
        )
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': encode_headers({
                'Content-Type': 'text/html; charset=UTF-8',
                'Etag': f'W/{digest}',
                'Cache-Control': 'no-cache',
            })
        })
        await send({
            'type': 'http.response.body',
            'body': body.encode()
        })

    @staticmethod
    async def not_modified(send, digest: str, cache_control: str = 'no-cache') -> []:
        await send({
            'type': 'http.response.start',
            'status': 304,
            'headers': encode_headers({
                'Etag': f'W/{digest}',
                'Cache-Control': cache_control
            })
        })
        await send({
            'type': 'http.response.body',
        })
        return

    @staticmethod
    async def not_found(send) -> None:
        await send({
            'type': 'http.response.start',
            'status': 404
        })
        await send({
            'type': 'http.response.body',
        })

    async def directory_listing(self, path_info, path) -> str:
        icon_path = join(self.prefix or '', 'markdown.svg')
        title = "Directory listing for %s" % path_info
        result = "<!DOCTYPE html><html><head>"
        result += f'<link rel="icon" type="image/x-icon" href="{icon_path}">'
        result += "<meta http-equiv=\"Content-Type\" content=\"text/html; charset=utf-8\">"
        result += "<title>" + title + "</title></head>"
        result += "<body><h1>" + title + "</h1><hr>"
        result += "<ul>"
        if path_info != '/':
            result += "<li><a href=\"../\"/>../</li>"

        async def ls(filter: Callable[[str], Awaitable[bool]]) -> AsyncGenerator[str, Any]:
            async def result():
                for entry in sorted(await listdir(path)):
                    if await filter(join(path, entry)):
                        yield entry

            return result()

        async for entry in await ls(isdir):
            result += '<li><a href="' + entry + '/' + '"/>' + entry + '/' + '</li>'

        async def file_filter(entry: str) -> bool:
            return await isfile(entry) and is_markdown(entry)

        async for entry in await ls(file_filter):
            result += '<li><a href="' + entry + '"/>' + entry + '</li>'
        return result

    async def stop(self):
        await self.file_watcher.stop()
        await self._client.aclose()
