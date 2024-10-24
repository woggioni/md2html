import logging
from logging.config import dictConfig as configure_logging

from yaml import safe_load

from .configuration import Configuration

with open(Configuration.instance.logging_configuration_file, 'r') as input_file:
    conf = safe_load(input_file)
    configure_logging(conf)


from pwo import Maybe
from .server import Server
from asyncio import get_running_loop
from .asgi_utils import decode_headers
from typing import Optional, Awaitable, Callable, Any, Mapping

log = logging.getLogger('access')
log.propagate = False

_server: Optional[Server] = None

async def application(scope, receive, send : Callable[[Mapping[str, Any]], Awaitable[None]]):
    global _server
    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                _server = Server(loop=get_running_loop(), prefix=None)
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await _server.stop()
                await send({'type': 'lifespan.shutdown.complete'})
    else:
        def maybe_log(evt):
            d = {
                'response_headers': (Maybe.of_nullable(evt.get('headers'))
                    .map(decode_headers)
                    .or_none()),
                'status': evt['status']
            }
            log.info(None, extra=dict(**{k : v for k, v in d.items() if k is not None}, **scope))
        def wrapped_send(*args, **kwargs):
            result = send(*args, **kwargs)
            (Maybe.of(args)
                .filter(lambda it: len(it) > 0)
                .map(lambda it: it[0])
                .filter(lambda it: it.get('type') == 'http.response.start')
                .if_present(maybe_log))
            return result
        pathsend = (Maybe.of_nullable(scope.get('extensions'))
                    .map(lambda it: it.get("http.response.pathsend"))
                    .is_present)
        await _server.handle_request(
            scope['method'],
            scope['path'],
            Maybe.of([header[1] for header in scope['headers'] if header[0].decode().lower() == 'if-none-match'])
                .filter(lambda it: len(it) > 0)
                .map(lambda it: it[0])
                .map(lambda it: it.decode())
                .or_else(None),
            Maybe.of_nullable(scope.get('query_string', None)).map(lambda it: it.decode()).or_else(None),
            wrapped_send,
            pathsend
        )

