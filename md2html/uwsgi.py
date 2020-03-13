import logging
from os import getcwd, listdir
from os.path import exists, splitext, isfile, join, relpath, isdir, basename, getmtime, dirname
from mimetypes import init as mimeinit, guess_type
import hashlib
from .md2html import compile_html
from shutil import which
from subprocess import Popen, PIPE, check_output

mimeinit()
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

cwd = getcwd()


def has_extension(filepath, extension):
    _, ext = splitext(filepath)
    return ext == extension


def is_markdown(filepath):
    return has_extension(filepath, ".md")


def is_dotfile(filepath):
    return has_extension(filepath, ".dot")


cache = dict()


def file_hash(filepath, bufsize=4096):
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


def application(env, start_response):
    path = join(cwd, relpath(env['PATH_INFO'], '/'))

    if exists(path):
        if isfile(path):
            cache_result = cache.get(path)
            _mtime = None

            def mtime():
                nonlocal _mtime
                if not _mtime:
                    _mtime = getmtime(path)
                return _mtime

            if not cache_result or cache_result[1] < mtime():
                digest = file_hash(path).hex()
                cache[path] = digest, mtime()
            else:
                digest = cache_result[0]

            def parse_etag(etag):
                if etag is None:
                    return
                start = etag.find('"')
                if start < 0:
                    return
                end = etag.find('"', start + 1)
                return etag[start + 1: end]

            etag = parse_etag(env.get('HTTP_IF_NONE_MATCH'))
            if etag and etag == digest:
                start_response('304 Not Modified', [
                    ('Etag', '"%s"' % digest),
                    ('Cache-Control', 'no-cache, must-revalidate, max-age=86400'),
                ])
                return []
            elif is_markdown(path):
                body = compile_html(path, ['extra', 'smarty', 'tables']).encode()
                start_response('200 OK', [('Content-Type', 'text/html; charset=UTF-8'),
                                          ('Etag', '"%s"' % digest),
                                          ('Cache-Control', 'no-cache, must-revalidate, max-age=86400'),
                                          ])
                return [body]
            elif is_dotfile(path) and which("dot"):
                body = check_output(['dot', '-Tsvg', basename(path)], cwd=dirname(path))
                start_response('200 OK', [('Content-Type', 'image/svg+xml; charset=UTF-8'),
                                          ('Etag', '"%s"' % digest),
                                          ('Cache-Control', 'no-cache, must-revalidate, max-age=86400'),
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

                start_response('200 OK', [('Content-Type', guess_type(basename(path))[0] or 'application/octet-stream'),
                                          ('Etag', '"%s"' % digest),
                                          ('Cache-Control', 'no-cache, must-revalidate, max-age=86400'),
                                          ])
                return read_file(path)
        elif isdir(path):
            body = directory_listing(env['PATH_INFO'], path).encode()
            start_response('200 OK', [
                ('Content-Type', 'text/html; charset=UTF-8'),
            ])
            return [body]
    start_response('404 NOT_FOUND', [])
    return []


def directory_listing(path_info, path):
    title = "Directory listing for %s" % path_info
    result = "<!DOCTYPE html><html><head>"
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
