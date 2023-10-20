import logging
from os import getcwd, listdir
from os.path import exists, splitext, isfile, join, relpath, isdir, basename, getmtime, dirname, normpath
from mimetypes import init as mimeinit, guess_type
import hashlib
from .md2html import compile_html, load_from_cache, STATIC_RESOURCES, MARDOWN_EXTENSIONS
from shutil import which
from subprocess import check_output
from io import BytesIO
from typing import Callable, TYPE_CHECKING, BinaryIO, Optional
from .file_watch import FileWatcher

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

    def handle_request(self, method: str, url_path: str, etag: Optional[str], query_string: Optional[str], start_response):
        if method != 'GET':
            start_response('405', [])
            return []
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
                return self.not_modified(start_response, digest, ('Cache-Control', 'must-revalidate, max-age=86400'))
            elif content:
                mime_type = guess_type(basename(url_path))[0] or 'application/octet-stream'
                start_response('200 OK', [
                    ('Content-Type', f'{mime_type}; charset=UTF-8'),
                    ('Etag', 'W/"%s"' % digest),
                    ('Cache-Control', 'must-revalidate, max-age=86400'),
                ])
                return content
        elif exists(path):
            if isfile(path):
                etag, digest = self.compute_etag_and_digest(
                    etag,
                    path,
                    lambda: open(path, 'rb'),
                    lambda: getmtime(path)
                )
                if etag and etag == digest:
                    if is_markdown(path) and query_string == 'reload':
                        subscription = self.file_watcher.subscribe(path)
                        try:
                            has_changed = subscription.wait(30)
                            if has_changed:
                                _, digest = self.compute_etag_and_digest(
                                    etag,
                                    path,
                                    lambda: open(path, 'rb'),
                                    lambda: getmtime(path)
                                )
                                if etag != digest:
                                    if exists(path) and isfile(path):
                                        return self.render_markdown(url_path, path, True, digest, start_response)
                                    else:
                                        return self.not_found(start_response)
                        finally:
                            subscription.unsubscribe()
                    return self.not_modified(start_response, digest)
                elif is_markdown(path):
                    raw = query_string == 'reload'
                    return self.render_markdown(url_path, path, raw, digest, start_response)
                elif is_dotfile(path) and which("dot"):
                    body = check_output(['dot', '-Tsvg', basename(path)], cwd=dirname(path))
                    start_response('200 OK', [('Content-Type', 'image/svg+xml; charset=UTF-8'),
                                              ('Etag', 'W/"%s"' % digest),
                                              ('Cache-Control', 'no-cache'),
                                              ])
                    return [body]
                else:
                    def read_file(file_path):
                        buffer_size = 1024
                        with open(file_path, 'rb') as f:
                            while True:
                                result = f.read(buffer_size)
                                if len(result) == 0:
                                    break
                                yield result

                    start_response('200 OK',
                                   [('Content-Type', guess_type(basename(path))[0] or 'application/octet-stream'),
                                    ('Etag', 'W/"%s"' % digest),
                                    ('Cache-Control', 'no-cache'),
                                    ])
                    return read_file(path)
            elif isdir(path):
                body = self.directory_listing(url_path, path).encode()
                start_response('200 OK', [
                    ('Content-Type', 'text/html; charset=UTF-8'),
                ])
                return [body]
        return self.not_found(start_response)

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
        if etag is None:
            return
        start = etag.find('"')
        if start < 0:
            return
        end = etag.find('"', start + 1)
        return etag[start + 1: end]

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

    def render_markdown(self,
                        url_path: 'StrOrBytesPath',
                        path: str,
                        raw: bool,
                        digest: str,
                        start_response) -> list[bytes]:
        body = compile_html(url_path,
                            path,
                            self.prefix,
                            MARDOWN_EXTENSIONS,
                            raw=raw).encode()
        start_response('200 OK', [('Content-Type', 'text/html; charset=UTF-8'),
                                  ('Etag', 'W/"%s"' % digest),
                                  ('Cache-Control', 'no-cache'),
                                  ])
        return [body]
    @staticmethod
    def not_modified(start_response, digest: str, cache_control=('Cache-Control', 'no-cache')) -> []:
        start_response('304 Not Modified', [
            ('Etag', f'W/"{digest}"'),
            cache_control,
        ])
        return []

    @staticmethod
    def not_found(start_response) -> list[bytes]:
        start_response('404 NOT_FOUND', [])
        return []

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
