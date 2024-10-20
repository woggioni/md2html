import logging
from os import getcwd, listdir
from os.path import exists, splitext, isfile, join, relpath, isdir, basename, getmtime, dirname, normpath
from mimetypes import init as mimeinit, guess_type
import hashlib
from .md2html import compile_html, load_from_cache, STATIC_RESOURCES, MARDOWN_EXTENSIONS
from shutil import which
import pygraphviz as pgv
from io import BytesIO
from typing import Callable, TYPE_CHECKING, BinaryIO, Optional
from .async_watchdog import FileWatcher
from pwo import Maybe

if TYPE_CHECKING:
    from _typeshed import StrOrBytesPath

mimeinit()

cwd: 'StrOrBytesPath' = getcwd()


def has_extension(filepath, extension):
    _, ext = splitext(filepath)
    return ext == extension


def is_markdown(filepath):
    return has_extension(filepath, ".md")


def is_dotfile(filepath):
    return has_extension(filepath, ".dot")


class Server:

    def __init__(self, root_dir: 'StrOrBytesPath' = getcwd(), prefix: Optional['StrOrBytesPath'] = None):
        self.root_dir = root_dir
        self.cache = dict['StrOrBytesPath', tuple[str, float]]()
        self.file_watcher = FileWatcher(cwd)
        self.logger = logging.getLogger(Server.__name__)
        self.prefix = prefix and normpath(f'{prefix.decode()}')

    async def handle_request(self, method: str, url_path: str, etag: Optional[str], query_string: Optional[str], send):
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
            content, mtime = load_from_cache(url_path)
            content = content.encode()
            etag, digest = self.compute_etag_and_digest(
                etag,
                url_path,
                lambda: BytesIO(content),
                lambda: mtime
            )
            if etag and etag == digest:
                await self.not_modified(send, digest, ('Cache-Control', 'must-revalidate, max-age=86400'))
                return
            elif content:
                mime_type = guess_type(basename(url_path))[0] or 'application/octet-stream'
                await send({
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [
                        (b'content-type', f'{mime_type}; charset=UTF-8'.encode()),
                        (b'etag', f'W/"{digest}"'.encode()),
                        (b'content-type', f'{mime_type}; charset=UTF-8'.encode()),
                        (b'Cache-Control', b'must-revalidate, max-age=86400'),
                    ]
                })
                await send({
                    'type': 'http.response.body',
                    'body': content
                })
                return
        elif exists(path):
            if isfile(path):
                etag, digest = self.compute_etag_and_digest(
                    etag,
                    path,
                    lambda: open(path, 'rb'),
                    lambda: getmtime(path)
                )
                self.logger.debug('%s %s', etag, digest)
                if etag and etag == digest:
                    if is_markdown(path) and query_string == 'reload':
                        subscription = self.file_watcher.subscribe(path)
                        try:
                            has_changed = await subscription.wait(30)
                            if has_changed:
                                _, digest = self.compute_etag_and_digest(
                                    etag,
                                    path,
                                    lambda: open(path, 'rb'),
                                    lambda: getmtime(path)
                                )
                                if etag != digest:
                                    if exists(path) and isfile(path):
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
                elif is_dotfile(path) and which("dot"):
                    graph = pgv.AGraph(path)
                    body = graph.draw(None, format="svg", prog="dot")
                    await send({
                        'type': 'http.response.start',
                        'status': 200,
                        'headers': (
                            (b'Content-Type', b'image/svg+xml; charset=UTF-8'),
                            (b'Etag', f'W/"{digest}"'.encode()),
                            (b'Cache-Control', b'no-cache'),
                        )
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': body
                    })
                else:
                    def read_file(file_path):
                        buffer_size = 1024
                        with open(file_path, 'rb') as f:
                            while True:
                                result = f.read(buffer_size)
                                if len(result) == 0:
                                    break
                                yield result

                    await send({
                        'type': 'http.response.start',
                        'status': 200,
                        'headers': (
                            (b'Content-Type', guess_type(basename(path))[0].encode() or b'application/octet-stream'),
                            (b'Etag', f'W/"{digest}"'),
                            (b'Cache-Control', b'no-cache')
                        )
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': read_file(path)
                    })
            elif isdir(path):
                body = self.directory_listing(url_path, path).encode()
                await send({
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': (
                        (b'Content-Type', b'text/html; charset=UTF-8'),
                    )
                })
                await send({
                    'type': 'http.response.body',
                    'body': body
                })
        else:
            await self.not_found(send)

    @staticmethod
    def stream_hash(source: BinaryIO, bufsize=0x1000) -> bytes:
        if bufsize <= 0:
            raise ValueError("Buffer size must be greater than 0")
        md5 = hashlib.md5()
        while True:
            buf = source.read(bufsize)
            if len(buf) == 0:
                break
            md5.update(buf)
        return md5.digest()

    @staticmethod
    def file_hash(filepath, bufsize=0x1000) -> bytes:
        if bufsize <= 0:
            raise ValueError("Buffer size must be greater than 0")
        md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            while True:
                buf = f.read(bufsize)
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

    def compute_etag_and_digest(
            self,
            etag_header: str,
            path: str,
            stream_source: Callable[[], BinaryIO],
            mtime_supplier: Callable[[], float]
    ) -> tuple[str, str]:
        cache_result = self.cache.get(path)
        _mtime: Optional[float] = None

        def mtime() -> float:
            nonlocal _mtime
            if not _mtime:
                _mtime = mtime_supplier()
            return _mtime

        if not cache_result or cache_result[1] < mtime():
            with stream_source() as stream:
                digest = Server.stream_hash(stream).hex()
            self.cache[path] = digest, mtime()
        else:
            digest = cache_result[0]

        etag = Server.parse_etag(etag_header)
        return etag, digest

    async def render_markdown(self,
                        url_path: 'StrOrBytesPath',
                        path: str,
                        raw: bool,
                        digest: str,
                        send) -> list[bytes]:
        body = compile_html(url_path,
                            path,
                            self.prefix,
                            MARDOWN_EXTENSIONS,
                            raw=raw).encode()
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': (
                (b'Content-Type', b'text/html; charset=UTF-8'),
                (b'Etag', f'W/{digest}'.encode()),
                (b'Cache-Control', b'no-cache'),
            )
        })
        await send({
            'type': 'http.response.body',
            'body': body
        })
        return
    @staticmethod
    async def not_modified(send, digest: str, cache_control=('Cache-Control', 'no-cache')) -> []:
        await send({
            'type': 'http.response.start',
            'status': 304,
            'headers': (
                (b'Etag', f'W/{digest}'.encode()),
                cache_control
            )
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

    def directory_listing(self, path_info, path) -> str:
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

        def ls(filter):
            return (entry for entry in sorted(listdir(path)) if filter(join(path, entry)))

        for entry in ls(isdir):
            result += '<li><a href="' + entry + '/' + '"/>' + entry + '/' + '</li>'
        for entry in ls(lambda entry: isfile(entry) and is_markdown(entry)):
            result += '<li><a href="' + entry + '"/>' + entry + '</li>'
        return result
