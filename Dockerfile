FROM alpine:latest AS base
LABEL org.opencontainers.image.authors=oggioni.walter@gmail.com
RUN --mount=type=cache,target=/var/cache/apk apk update
RUN --mount=type=cache,target=/var/cache/apk apk add python3 py3-pip graphviz

FROM base AS build
RUN --mount=type=cache,target=/var/cache/apk apk add musl-dev gcc graphviz-dev git
RUN adduser -D luser
USER luser
WORKDIR /home/luser
COPY --chown=luser:users ./requirements-dev.txt ./requirements-dev.txt
COPY --chown=luser:users ./requirements-run.txt ./requirements-run.txt
WORKDIR /home/luser/
RUN python -m venv .venv
RUN --mount=type=cache,target=/home/luser/.cache/pip,uid=1000,gid=1000 .venv/bin/pip wheel -w /home/luser/wheel pygraphviz
RUN --mount=type=cache,target=/home/luser/.cache/pip,uid=1000,gid=1000 .venv/bin/pip install -r requirements-dev.txt /home/luser/wheel/*.whl
COPY --chown=luser:users . /home/luser/bugis
WORKDIR /home/luser/bugis
RUN rm -rf .venv dist build
RUN --mount=type=cache,target=/home/luser/.cache/pip,uid=1000,gid=1000 /home/luser/.venv/bin/python -m build

FROM base AS release
RUN mkdir /srv/http
RUN adduser -D -h /var/lib/bugis -u 1000 bugis
USER bugis
WORKDIR /var/lib/bugis
COPY --chown=bugis:users conf/pip.conf ./.pip/pip.conf
RUN python -m venv .venv
RUN --mount=type=cache,target=/var/bugis/.cache/pip,uid=1000,gid=1000 --mount=type=bind,ro,from=build,source=/home/luser/requirements-run.txt,target=/requirements-run.txt --mount=type=bind,ro,from=build,source=/home/luser/wheel,target=/wheel .venv/bin/pip install -r /requirements-run.txt /wheel/*.whl
RUN --mount=type=cache,target=/var/bugis/.cache/pip,uid=1000,gid=1000 --mount=type=bind,ro,from=build,source=/home/luser/bugis/dist,target=/dist .venv/bin/pip install /dist/*.whl
VOLUME /srv/http
WORKDIR /srv/http

ENV GRANIAN_HOST=0.0.0.0
ENV GRANIAN_PORT=8000
ENV GRANIAN_INTERFACE=asgi
ENV GRANIAN_LOOP=asyncio
ENV GRANIAN_LOG_ENABLED=false

ENTRYPOINT ["/var/lib/bugis/.venv/bin/python", "-m", "granian", "bugis.asgi:application"]
EXPOSE 8000/tcp

