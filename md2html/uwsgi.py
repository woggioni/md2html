import logging
from os import getcwd, listdir
from os.path import exists, splitext, isfile, join, relpath, isdir

import hashlib
from .md2html import compile_html

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


cwd = getcwd()

def is_markdown(filepath):
    _, ext = splitext(filepath)
    return ext == ".md"

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
        if isfile(path) and is_markdown(path):
            if path not in cache:
                digest = file_hash(path).hex()
                cache[path] = digest
            else:
                digest = cache[path]
            etag = env.get('HTTP_IF_NONE_MATCH')
            if etag and etag[1:-1] == digest:
                start_response('301 Not Modified', [
                    ('Content-Type', 'text/html'),
                    ('Content-Length', str(0)),
                    ('Cache-Control', 'no-cache, must-revalidate, max-age=86400'),
                    ('Connection', 'keep-alive')
                ])
                return []
            else:
                body = compile_html(path, ['extra', 'smarty', 'tables']).encode()
                start_response('200 OK', [('Content-Type', 'text/html'),
                                          ('Content-Length', str(len(body))),
                                          ('Etag', '"%s"' % digest),
                                          ('Cache-Control', 'no-cache, must-revalidate, max-age=86400'),
                                          ('Connection',  'keep-alive'),
                                          ])
                return [body]
        elif isdir(path):
            body = directory_listing(env['PATH_INFO'], path).encode()
            start_response('200 OK', [
                ('Content-Type', 'text/html'), ('Content-Length', str(len(body))), ('Connection', 'keep-alive'),
            ])
            return [body]
    start_response('404 NOT_FOUND', [('Content-Length', str(0)), ('Connection',  'keep-alive')])
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
