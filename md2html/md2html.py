#!/usr/bin/env python3

import argparse
import hashlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, socketserver, HTTPServer
from os.path import basename, dirname, abspath, join
from urllib.parse import urlparse

import markdown

STATIC_CACHE = {}


def load_from_cache(path):
    global STATIC_CACHE
    if path not in STATIC_CACHE:
        with open(join(dirname(__file__), 'static') + path, 'r') as static_file:
            STATIC_CACHE[path] = static_file.read()
    return STATIC_CACHE[path]


def compile_html(mdfile=None, extensions=None, raw=None, **kwargs):
    html = None
    with mdfile and open(mdfile, 'r') or sys.stdin as instream:
        html = markdown.markdown(instream.read(), extensions=extensions, output_format='html5')
    if raw:
        doc = html
    else:
        css = '        <style>%s\n%s\n        </style>' % (
            load_from_cache('/github-markdown.css'),
            load_from_cache('/custom.css')
        )
        doc = load_from_cache('/template.html').format(content=html, script='', css=css)
    return doc


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    pass


class MarkdownHTTPServer(ThreadingHTTPServer):

    def __init__(self, mdfile, extensions=(), handler=BaseHTTPRequestHandler, interface="127.0.0.1", port=8080):
        import inotify
        import inotify.adapters
        import signal

        self.stop = False

        def sigint_handler(signum, frame):
            self.stop = True

        handlers = (sigint_handler, signal.getsignal(signal.SIGINT))
        signal.signal(signal.SIGINT, lambda signum, frame: [handler(signum, frame) for handler in handlers])

        self.mdfile = mdfile
        self.extensions = extensions
        self.condition_variable = threading.Condition()
        self.hash = None
        self.etag = None

        def watch_file():
            watcher = inotify.adapters.Inotify()
            watcher.add_watch(dirname(abspath(self.mdfile)))
            target_file = basename(self.mdfile)
            while True:
                if self.stop:
                    break
                for event in watcher.event_gen(yield_nones=True, timeout_s=1):
                    if not event:
                        continue
                    (_, event_type, path, filename) = event
                    if filename == target_file and len(set(event_type).intersection(
                            {'IN_CLOSE_WRITE'})):
                        self.condition_variable.acquire()
                        if self.update_file_digest():
                            self.condition_variable.notify_all()
                        self.condition_variable.release()

        file_watcher = threading.Thread(target=watch_file)
        file_watcher.start()
        super().__init__((interface, port), handler)

    def update_file_digest(self):
        md5 = hashlib.md5()
        with open(self.mdfile, 'rb') as mdfile:
            md5.update(mdfile.read())
        digest = md5.digest()
        if not self.hash or self.hash != digest:
            self.hash = digest
            self.etag = md5.hexdigest()
            return True
        else:
            return False


class MarkdownRequestHandler(BaseHTTPRequestHandler):
    status_map = {
        200: "OK",
        204: "No Content",
        304: "Not Modified",
        400: "Bad Request",
        401: "Unauthorized",
        404: "Not Found",
        499: "Service Error",
        500: "Internal Server Error",
        501: "Not Implemented",
        503: "Service Unavailable"
    }

    def answer(self, code, reply=None, content_type="text/plain",
               headers=()):
        output = self.wfile
        if not reply:
            reply = MarkdownRequestHandler.status_map[code]
        try:
            self.send_response(code, MarkdownRequestHandler.status_map[code])
            for header in headers:
                self.send_header(*header)
            self.send_header("Content-Type", content_type)
            self.send_header('Content-Length', len(reply))
            self.end_headers()
            output.write(reply.encode("UTF-8"))
            output.flush()
        except BrokenPipeError:
            pass

    def markdown_answer(self):
        if not self.server.etag:
            self.server.condition_variable.acquire()
            self.server.update_file_digest()
            self.server.condition_variable.release()
        self.answer(200, headers=(('Etag', self.server.etag),),
                    reply=compile_html(mdfile=self.server.mdfile, extensions=self.server.extensions, raw=True),
                    content_type='text/html')

    def do_GET(self):
        path = urlparse(self.path)
        if path.path == '/':
            self.answer(200, reply=load_from_cache('/template.html').format(
                content='',
                script='<script src="/hot-reload.js", type="text/javascript"></script>',
                css='<link rel="stylesheet" href="github-markdown.css">'
                    '<link rel="stylesheet" href="custom.css">'),
                        content_type='text/html')
        elif path.path in {'/github-markdown.css', '/custom.css', '/hot-reload.js'}:
            self.answer(200, load_from_cache(path.path), content_type='text/css')
        elif path.path == '/markdown':
            self.markdown_answer()
        elif path.path == '/reload':
            if 'If-None-Match' not in self.headers or self.headers['If-None-Match'] != self.server.etag:
                self.markdown_answer()
            else:
                self.server.condition_variable.acquire()
                self.server.condition_variable.wait(timeout=10)
                self.server.condition_variable.release()
                if self.server.stop:
                    self.answer(503)
                elif self.headers['If-None-Match'] == self.server.etag:
                    self.answer(304)
                else:
                    self.answer(200, headers=(('Etag', self.server.etag),),
                                reply=compile_html(mdfile=self.server.mdfile,
                                                   extensions=self.server.extensions,
                                                   raw=True),
                                content_type='text/html')
        else:
            self.answer(404)


def parse_args(args=None):
    parser = argparse.ArgumentParser(description='Make a complete, styled HTML document from a Markdown file.')
    parser.add_argument('mdfile', help='File to convert. Defaults to stdin.')
    parser.add_argument('-o', '--out', help='Output file name. Defaults to stdout.')
    parser.add_argument('-r', '--raw', action='store_true',
                        help='Just output a raw html fragment, as returned from the markdown module')
    parser.add_argument('-e', '--extensions', nargs='+', default=['extra', 'smarty', 'tables'],
                        help='Activate specified markdown extensions (defaults to "extra smarty tables")')

    try:
        import inotify
        import gevent
        import signal
        parser.add_argument('-w', '--watch', action='store_true',
                            help='Watch specified source file and rerun the compilation for every time it changes')
        parser.add_argument('-p', '--port', default=5000, type=int,
                            help='Specify http server port (defaults to 5000)')
        parser.add_argument('-i', '--interface', default='',
                            help='Specify http server listen interface (defaults to localhost)')
    except ImportError:
        pass
    return parser.parse_args(args)


def write_html(out=None, **kwargs):
    doc = compile_html(**kwargs)
    with (out and open(out, 'w')) or sys.stdout as outstream:
        outstream.write(doc)


def main(args=None):
    args = parse_args(args)
    if hasattr(args, 'watch') and args.watch:
        server = MarkdownHTTPServer(args.mdfile,
                                    extensions=args.extensions,
                                    interface=args.interface,
                                    port=args.port,
                                    handler=MarkdownRequestHandler)
        server.serve_forever()
    else:
        write_html(**vars(args))


if __name__ == '__main__':
    main()
