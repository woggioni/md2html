import logging
from logging.config import dictConfig as configure_logging
from os import environ
from pathlib import Path

from pwo import Maybe
from yaml import safe_load
from .server import Server

logging_configuration_file = environ.get("LOGGING_CONFIGURATION_FILE", Path(__file__).parent / 'default-conf' / 'logging.yaml')
with open(logging_configuration_file, 'r') as input_file:
    conf = safe_load(input_file)
    configure_logging(conf)


log = logging.getLogger(__name__)

_server = None
async def application(ctx, receive, send):
    global _server
    if _server is None:
        _server = Server(prefix=None)
    log.info(None, extra=ctx)
    await _server.handle_request(
        ctx['method'],
        ctx['path'],
        Maybe.of([header[1] for header in ctx['headers'] if header[0].decode().lower() == 'if-none-match'])
            .filter(lambda it: len(it) > 0)
            .map(lambda it: it[0])
            .map(lambda it: it.decode())
            .or_else(None),
        Maybe.of_nullable(ctx.get('query_string', None)).map(lambda it: it.decode()).or_else(None),
        send
    )

