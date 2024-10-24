from os import environ
from pathlib import Path
from dataclasses import dataclass, field, asdict
from granian.constants import Loops, Interfaces, ThreadModes, HTTPModes, StrEnum
from granian.log import LogLevels
from granian.http import HTTP1Settings, HTTP2Settings
from typing import Optional, Sequence, Dict, Any
from pwo import classproperty, Maybe
from yaml import add_representer, SafeDumper, SafeLoader


@dataclass(frozen=True)
class Configuration:
    logging_configuration_file: str = environ.get("LOGGING_CONFIGURATION_FILE",
                                                  Path(__file__).parent / 'default-conf' / 'logging.yaml')
    plant_uml_server_address: str = environ.get('PLANT_UML_SERVER_ADDRESS', None)

    @classproperty
    def instance(cls) -> 'Configuration':
        return Configuration()

    @dataclass(frozen=True)
    class GranianConfiguration:
        address: str = '127.0.0.1'
        port: int = 8000
        interface: str = Interfaces.ASGI
        workers: int = 1
        threads: int = 1
        blocking_threads: Optional[int] = None
        threading_mode: ThreadModes = ThreadModes.workers
        loop: Loops = Loops.auto
        loop_opt: bool = False
        http: HTTPModes = HTTPModes.auto
        websockets: bool = True
        backlog: int = 1024
        backpressure: Optional[int] = None
        http1_settings: Optional[HTTP1Settings] = None
        http2_settings: Optional[HTTP2Settings] = None
        log_enabled: bool = True
        log_level: LogLevels = LogLevels.info
        log_dictconfig: Optional[Dict[str, Any]] = None
        log_access: bool = False
        log_access_format: Optional[str] = None
        ssl_cert: Optional[Path] = None
        ssl_key: Optional[Path] = None
        ssl_key_password: Optional[str] = None
        url_path_prefix: Optional[str] = None
        respawn_failed_workers: bool = False
        respawn_interval: float = 3.5
        workers_lifetime: Optional[int] = None
        factory: bool = False
        reload: bool = False
        reload_paths: Optional[Sequence[Path]] = None
        reload_ignore_dirs: Optional[Sequence[str]] = None
        reload_ignore_patterns: Optional[Sequence[str]] = None
        reload_ignore_paths: Optional[Sequence[Path]] = None
        process_name: Optional[str] = None
        pid_file: Optional[Path] = None

        @staticmethod
        def from_dict(d) -> 'Configuration.GranianConfiguration':
            return Configuration.GranianConfiguration(**{k: v for k, v in dict(
                address=d.get('address', None),
                port=d.get('port', None),
                interface=Maybe.of_nullable(d.get('interface')).map(lambda it: Interfaces(it)).or_else(None),
                workers=d.get('workers', None),
                threads=d.get('threads', None),
                blocking_threads=d.get('blocking_threads', None),
                threading_mode=Maybe.of_nullable(d.get('threading_modes')).map(lambda it: ThreadModes(it)).or_else(None),
                loop=Maybe.of_nullable(d.get('loop')).map(lambda it: Loops(it)).or_else(None),
                loop_opt=d.get('loop_opt', None),
                http=Maybe.of_nullable(d.get('http')).map(lambda it: HTTPModes(it)).or_else(None),
                websockets=d.get('websockets', None),
                backlog=d.get('backlog', None),
                backpressure=d.get('backpressure', None),
                http1_settings=Maybe.of_nullable(d.get('http1_settings')).map(lambda it: HTTP1Settings(**it)).or_else(None),
                http2_settings=Maybe.of_nullable(d.get('http2_settings')).map(lambda it: HTTP2Settings(**it)).or_else(None),
                log_enabled=d.get('log_enabled', None),
                log_level=Maybe.of_nullable(d.get('log_level')).map(lambda it: LogLevels(it)).or_else(None),
                # log_dictconfig: Optional[Dict[str, Any]] = None,
                log_access=d.get('log_access', None),
                log_access_format=d.get('log_access_format', None),
                ssl_cert=d.get('ssl_cert', None),
                ssl_key=d.get('ssl_key', None),
                ssl_key_password=d.get('ssl_key_password', None),
                url_path_prefix=d.get('url_path_prefix', None),
                respawn_failed_workers=d.get('respawn_failed_workers', None),
                respawn_interval=d.get('respawn_interval', None),
                workers_lifetime=d.get('workers_lifetime', None),
                factory=d.get('factory', None),
                reload=d.get('reload', None),
                reload_paths=d.get('reload_paths', None),
                reload_ignore_dirs=d.get('reload_ignore_dirs', None),
                reload_ignore_patterns=d.get('reload_ignore_patterns', None),
                reload_ignore_paths=d.get('reload_ignore_paths', None),
                process_name=d.get('process_name', None),
                pid_file=d.get('pid_file', None),
            ).items() if v is not None})

    granian: GranianConfiguration = GranianConfiguration()

    @staticmethod
    def from_dict(d) -> 'Configuration':
        return Configuration(
            **{k: v for k, v in dict(
                logging_configuration_file=d.get('logging_configuration_file', None),
                plant_uml_server_address=d.get('plant_uml_server_address', None),
                granian=Maybe.of_nullable(d.get('granian'))
                .map(Configuration.GranianConfiguration.from_dict)
                .or_else(None)
            ).items() if v is not None
               }
        )

    def to_yaml(self, stream):
        dumper = SafeDumper(stream)
        dumper.add_representer(Configuration, lambda dumper, conf: dumper.represent_dict(asdict(conf)))
        dumper.add_representer(Configuration.GranianConfiguration,
                               lambda dumper, conf: dumper.represent_dict(asdict(conf)))
        dumper.add_representer(LogLevels, lambda dumper, level: dumper.represent_str(level.lower()))
        dumper.add_multi_representer(Path, lambda dumper, path: dumper.represent_str(str(path)))
        dumper.add_multi_representer(StrEnum, lambda dumper, str_enum: dumper.represent_str(str(str_enum)))
        dumper.add_representer(HTTP1Settings, lambda dumper, settings: dumper.represent_dict(vars(settings)))
        dumper.add_representer(HTTP2Settings, lambda dumper, settings: dumper.represent_dict(vars(settings)))

        try:
            dumper.open()
            dumper.represent(Configuration.instance)
            dumper.close()
        finally:
            dumper.dispose()

    @staticmethod
    def from_yaml(stream) -> 'Configuration':
        loader = SafeLoader(stream)
        try:
            conf = loader.get_single_data()
            return Configuration.from_dict(conf)
        finally:
            loader.dispose()
