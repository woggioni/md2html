#!/usr/bin/env python3

import argparse
import sys
import markdown
from os.path import basename, dirname
import json

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <link href="http://netdna.bootstrapcdn.com/twitter-bootstrap/2.3.0/css/bootstrap-combined.min.css" rel="stylesheet">
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
        let eventSource = new EventSource("/stream");
        eventSource.addEventListener('reload', function(e) {{
                window.location.reload(true);
        }});
    </script>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""


class ServerSentEvent(object):

    def __init__(self, id=None, event=None, data=None, retry=1000):
        self.id = id
        self.event = event
        self.data = json.dumps(data)
        self.retry = retry

    def encode(self):
        if not self.data:
            return ""
        lines = [f"{key}: {value}" for key, value in vars(self).items() if value]
        return "%s\n\n" % "\n".join(lines)

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
        import flask
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

def compile_html(mdfile=None, extensions=None, raw=None, **kwargs):
    html = None
    with mdfile and open(mdfile, 'r') or sys.stdin as instream:
        html = markdown.markdown(instream.read(), extensions=extensions, output_format='html5')
    if raw:
        doc = html
    else:
        doc = TEMPLATE.format(**dict(content=html))
    return doc

def write_html(out=None, **kwargs):
    doc = compile_html(**kwargs)
    with (out and open(out, 'w')) or sys.stdout as outstream:
        outstream.write(doc)

def main(args=None):
    import signal
    args = parse_args(args)
    exit = False
    def sigint_handler(signum, frame):
        nonlocal exit
        exit = True
    handlers = (sigint_handler, signal.getsignal(signal.SIGINT))
    signal.signal(signal.SIGINT, lambda signum, frame: [handler(signum, frame) for handler in handlers])
    if hasattr(args, 'watch') and args.watch:
        import threading
        from flask import Flask, Response
        from gevent.pywsgi import WSGIServer
        condition_variable = threading.Condition()
        def watch_file():
            import inotify.adapters
            nonlocal condition_variable, exit
            watcher = inotify.adapters.Inotify()
            watcher.add_watch(dirname(args.mdfile))
            target_file = basename(args.mdfile)
            while True:
                if exit:
                    break
                for event in watcher.event_gen(yield_nones=True, timeout_s=1):
                    if not event:
                        continue
                    (_, event_type, path, filename) = event
                    if filename == target_file and len(set(event_type).intersection(
                            {'IN_CREATE', 'IN_MODIFY', 'IN_CLOSE_WRITE'})):
                        condition_variable.acquire()
                        condition_variable.notify_all()
                        condition_variable.release()

        file_watcher = threading.Thread(target=watch_file)
        file_watcher.start()
        app = Flask(__name__)
        @app.route('/')
        def get():
            return Response(compile_html(**vars(args)), mimetype='text/html')

        @app.route("/stream")
        def stream():
            nonlocal condition_variable
            def gen():
                while True:
                    condition_variable.acquire()
                    condition_variable.wait()
                    sse = ServerSentEvent(event='reload')
                    return sse.encode()
            return Response(gen(), mimetype="text/event-stream")

        server = WSGIServer((args.interface, args.port), app, environ={'wsgi.multithread': True})
        server.serve_forever()
    else:
        write_html(**vars(args))

if __name__ == '__main__':
    main()
