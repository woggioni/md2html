FROM alpine:latest AS base
LABEL org.opencontainers.image.authors=oggioni.walter@gmail.com
RUN --mount=type=cache,target=/var/cache/apk apk update
RUN --mount=type=cache,target=/var/cache/apk apk add python3 py3-pip graphviz

FROM base AS build
RUN --mount=type=cache,target=/var/cache/apk apk add musl-dev gcc graphviz-dev
RUN adduser -D luser
USER luser
WORKDIR /home/luser
COPY --chown=luser:users ./requirements-dev.txt ./bugis/requirements-dev.txt
COPY --chown=luser:users ./src ./bugis/src
COPY --chown=luser:users ./pyproject.toml ./bugis/pyproject.toml
WORKDIR /home/luser/bugis
RUN python -m venv .venv
RUN --mount=type=cache,target=/home/luser/.cache/pip,uid=1000,gid=1000 .venv/bin/pip wheel -w /home/luser/wheel -r requirements-dev.txt pygraphviz
RUN --mount=type=cache,target=/home/luser/.cache/pip,uid=1000,gid=1000 .venv/bin/pip install -r requirements-dev.txt /home/luser/wheel/*.whl
RUN --mount=type=cache,target=/home/luser/.cache/pip,uid=1000,gid=1000 .venv/bin/python -m build

FROM base AS release
RUN mkdir /srv/http
RUN adduser -D -h /var/bugis -u 1000 bugis
USER bugis
WORKDIR /var/bugis
COPY --chown=bugis:users conf/pip.conf ./.pip/pip.conf
RUN python -m venv .venv
RUN --mount=type=cache,target=/var/bugis/.cache/pip,uid=1000,gid=1000 --mount=type=bind,ro,source=./requirements-run.txt,target=/requirements-run.txt --mount=type=bind,ro,from=build,source=/home/luser/wheel,target=/wheel .venv/bin/pip install -r /requirements-run.txt /wheel/*.whl
RUN --mount=type=cache,target=/var/bugis/.cache/pip,uid=1000,gid=1000 --mount=type=bind,ro,from=build,source=/home/luser/bugis/dist,target=/dist .venv/bin/pip install /dist/*.whl
VOLUME /srv/http
WORKDIR /srv/http

ENV GRANIAN_HOST=0.0.0.0
ENV GRANIAN_INTERFACE=asginl
ENV GRANIAN_LOOP=asyncio
ENV GRANIAN_LOOP=asyncio
ENV GRANIAN_LOG_ENABLED=false

ENTRYPOINT ["/var/bugis/.venv/bin/python", "-m", "granian", "bugis.asgi:application"]
EXPOSE 8000/tcp

