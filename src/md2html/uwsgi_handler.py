import logging
from .server import Server
from uwsgi import log
class UwsgiHandler(logging.Handler):

    def emit(self, record: logging.LogRecord) -> None:
        log(self.formatter.format(record))


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(threadName)s] (%(name)s) %(levelname)s %(message)s',
    handlers=[UwsgiHandler()]
)

server = Server()

def application(env, start_response):
    return server.handle_request(
        env['REQUEST_METHOD'],
        env['PATH_INFO'],
        env.get('HTTP_IF_NONE_MATCH', None),
        env.get('QUERY_STRING', None),
        start_response
    )
