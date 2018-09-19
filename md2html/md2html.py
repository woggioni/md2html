#!/usr/bin/env python3

import argparse
import hashlib
import sys
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from os.path import basename, dirname, abspath
from urllib.parse import urlparse

import markdown

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    {css}
    <style>
        body {{
            font-family: sans-serif;
        }}
        code, pre {{
            font-family: monospace;
        }}
        h1 code,
        h2 code,
        h3 code,
        h4 code,
        h5 code,
        h6 code {{
            font-size: inherit;
        }}
    </style>
</head>
<body>
    <script type=\"text/javascript\">
        function req(first) {{
            var xmlhttp = new XMLHttpRequest();
            xmlhttp.onload = function() {{
                if (xmlhttp.status == 200) {{
                    document.querySelector("div.container").innerHTML = xmlhttp.responseText;
                }} else if(xmlhttp.status == 304) {{
                }} else {{
                    console.log(xmlhttp.status, xmlhttp.statusText);
                }}
                req(false);
            }};
            xmlhttp.onerror = function() {{
                console.log(xmlhttp.status, xmlhttp.statusText);
                setTimeout(req, 1000, false);
            }};
            xmlhttp.open("GET", first ? "/markdown" : "/reload", true);
            xmlhttp.send();
        }}
        req(true);
    </script>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""

def create_css_tag(url_list):
    result = ''
    for url in url_list:
        result += '<link href="%s" rel="stylesheet">' % url
    return result

def compile_html(mdfile=None, extensions=None, raw=None, stylesheet=(), **kwargs):
    html = None
    with mdfile and open(mdfile, 'r') or sys.stdin as instream:
        html = markdown.markdown(instream.read(), extensions=extensions, output_format='html5')
    if raw:
        doc = html
    else:
        doc = TEMPLATE.format(content=html, css=create_css_tag(stylesheet))
    return doc

class MarkdownHTTPServer(ThreadingHTTPServer):

    def __init__(self, mdfile, extensions=(), stylesheet=(), handler=BaseHTTPRequestHandler, interface="127.0.0.1", port=8080):
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
        self.stylesheet = stylesheet
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
            self.answer(200, reply=TEMPLATE.format(content='', css=create_css_tag(self.server.stylesheet)),
                             content_type='text/html')
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
        parser.add_argument('-s', '--stylesheet', nargs='+',
                            default=['http://netdna.bootstrapcdn.com/twitter-bootstrap/2.3.0/css/bootstrap-combined.min.css'],
                            help='Specify a list of stylesheet URLs to add to the html page')
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
                                    stylesheet=args.stylesheet,
                                    interface=args.interface,
                                    port=args.port,
                                    handler=MarkdownRequestHandler)
        server.serve_forever()
    else:
        write_html(**vars(args))

if __name__ == '__main__':
    main()
