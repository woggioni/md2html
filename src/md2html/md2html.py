import sys
from os.path import dirname, join
from time import time
from typing import Optional

import markdown

STATIC_RESOURCES: set[str] = {
    '/github-markdown.css',
    '/custom.css',
    '/hot-reload.js',
    '/pygment.css',
}
STATIC_CACHE: dict[str, tuple[str, float]] = {}

MARDOWN_EXTENSIONS = ['extra', 'smarty', 'tables', 'codehilite']

def load_from_cache(path) -> tuple[str, float]:
    global STATIC_CACHE
    if path not in STATIC_CACHE:
        with open(join(dirname(__file__), 'static') + path, 'r') as static_file:
            STATIC_CACHE[path] = (static_file.read(), time())
    return STATIC_CACHE[path]


def compile_html(mdfile=None,
                 extensions: Optional[list[str]] = None,
                 raw: bool = False) -> str:
    with mdfile and open(mdfile, 'r') or sys.stdin as instream:
        html = markdown.markdown(instream.read(), extensions=extensions, output_format='html')
    if raw:
        doc = html
    else:
        css = '        <style>% s\n%s\n%s\n        </style>' % (
            load_from_cache('/github-markdown.css')[0],
            load_from_cache('/pygment.css')[0],
            load_from_cache('/custom.css')[0],
        )
        script = '<script src="/hot-reload.js", type="text/javascript" defer="true"></script>'
        doc = load_from_cache('/template.html')[0].format(content=html, script=script, css=css)
    return doc
