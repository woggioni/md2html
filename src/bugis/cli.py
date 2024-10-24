import argparse
from dataclasses import asdict
from os import environ
from pathlib import Path
from typing import Optional, Sequence

import yaml
from granian import Granian
from pwo import Maybe

from .configuration import Configuration


def main(args: Optional[Sequence[str]] = None):
    parser = argparse.ArgumentParser(description="A simple CLI program to render Markdown files")
    default_configuration_file = (Maybe.of(environ.get('XDG_CONFIG_HOME'))
                                  .map(lambda it: Path(it))
                                  .map(lambda it: it / 'bugis' / 'bugis.yaml')
                                  .or_else_get(lambda: Path(environ.get('HOME')) / '.config' / 'bugis' / 'bugis.yaml')
                                  .filter(Path.exists)
                                  .or_else(None)
    )
    parser.add_argument(
        '-c',
        '--configuration',
        help='Path to the configuration file',
        default=default_configuration_file,
        type=Path,
    )
    args = parser.parse_args(args)

    def parse(configuration: Path):
        with open(configuration, 'r') as f:
            return Configuration.from_dict(yaml.safe_load(f))

    conf = Maybe.of_nullable(args.configuration).map(parse).or_else(Configuration.instance)

    Granian(
        "bugis.asgi:application",
        **asdict(conf.granian)
    ).serve()