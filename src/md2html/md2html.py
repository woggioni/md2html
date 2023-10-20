import sys
from os.path import dirname, join, relpath
from time import time
from typing import Optional, TYPE_CHECKING

import markdown

if TYPE_CHECKING:
    from _typeshed import StrOrBytesPath

STATIC_RESOURCES: set[str] = {
    '/github-markdown.css',
    '/custom.css',
    '/hot-reload.js',
    '/pygment.css',
    '/markdown.svg'
}
STATIC_CACHE: dict[str, tuple[str, float]] = {}

MARDOWN_EXTENSIONS = ['extra', 'smarty', 'tables', 'codehilite']


def load_from_cache(path) -> tuple[str, float]:
    global STATIC_CACHE
    if path not in STATIC_CACHE:
        with open(join(dirname(__file__), 'static') + path, 'r') as static_file:
            STATIC_CACHE[path] = (static_file.read(), time())
    return STATIC_CACHE[path]


def compile_html(url_path,
                 mdfile: 'StrOrBytesPath',
                 prefix: Optional['StrOrBytesPath'] = None,
                 extensions: Optional[list[str]] = None,
                 raw: bool = False) -> str:
    with mdfile and open(mdfile, 'r') or sys.stdin as instream:
        html = markdown.markdown(instream.read(), extensions=extensions, output_format='html')
    if raw:
        doc = html
    else:
        parent = dirname(url_path)
        prefix = prefix or relpath('/', start=parent)
        script = f'<script src="{prefix}/hot-reload.js", type="text/javascript" defer="true"></script>'
        css = f'<link rel="icon" type="image/x-icon" href="{prefix}/markdown.svg">'
        for css_file in ('github-markdown.css', 'pygment.css', 'custom.css'):
            css += f'        <link rel="stylesheet" href="{prefix}/{css_file}">'
        doc = load_from_cache('/template.html')[0].format(content=html, script=script, css=css)
    return doc
