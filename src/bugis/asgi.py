import logging
from logging.config import dictConfig as configure_logging
from os import environ
from yaml import safe_load
from pathlib import Path

logging_configuration_file = environ.get("LOGGING_CONFIGURATION_FILE", Path(__file__).parent / 'default-conf' / 'logging.yaml')
with open(logging_configuration_file, 'r') as input_file:
    conf = safe_load(input_file)
    configure_logging(conf)


from pwo import Maybe
from .server import Server
from asyncio import get_running_loop

log = logging.getLogger('access')
log.propagate = False

_server = None

def decode_headers(headers):
    result = dict()
    for key, value in headers:
        if isinstance(key, bytes):
            key = key.decode()
        if isinstance(value, bytes):
            value = value.decode()
        l = result.setdefault(key, list())
        l.append(value)
    return {
        k: tuple(v) for k, v in result.items()
    }

async def application(ctx, receive, send):
    global _server
    if _server is None:
        _server = Server(loop=get_running_loop(), prefix=None)

    def maybe_log(evt):
        d = {
            'response_headers': (Maybe.of_nullable(evt.get('headers'))
                .map(decode_headers)
                .or_none()),
            'status': evt['status']
        }
        log.info(None, extra=dict(**{k : v for k, v in d.items() if k is not None}, **ctx))
    def wrapped_send(*args, **kwargs):
        result = send(*args, **kwargs)
        (Maybe.of(args)
            .filter(lambda it: len(it) > 0)
            .map(lambda it: it[0])
            .filter(lambda it: it.get('type') == 'http.response.start')
            .if_present(maybe_log))
        return result
    await _server.handle_request(
        ctx['method'],
        ctx['path'],
        Maybe.of([header[1] for header in ctx['headers'] if header[0].decode().lower() == 'if-none-match'])
            .filter(lambda it: len(it) > 0)
            .map(lambda it: it[0])
            .map(lambda it: it.decode())
            .or_else(None),
        Maybe.of_nullable(ctx.get('query_string', None)).map(lambda it: it.decode()).or_else(None),
        wrapped_send
    )

