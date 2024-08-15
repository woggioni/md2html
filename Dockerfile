FROM alpine:latest AS base
LABEL org.opencontainers.image.authors=oggioni.walter@gmail.com
RUN --mount=type=cache,target=/var/cache/apk apk update
RUN --mount=type=cache,target=/var/cache/apk apk add python3 py3-pip uwsgi uwsgi-python3 graphviz uwsgi-gevent3

FROM base AS build
RUN adduser -D luser
USER luser
WORKDIR /home/luser
COPY --chown=luser:users ./requirements-dev.txt ./md2html/requirements-dev.txt
COPY --chown=luser:users ./src ./md2html/src
COPY --chown=luser:users ./pyproject.toml ./md2html/pyproject.toml
WORKDIR /home/luser/md2html
RUN python -m venv venv
RUN --mount=type=cache,target=/home/luser/.cache/pip,uid=1000,gid=1000 venv/bin/pip install -r requirements-dev.txt
RUN --mount=type=cache,target=/home/luser/.cache/pip,uid=1000,gid=1000 venv/bin/python -m build

FROM base AS release
RUN mkdir /srv/http
RUN adduser -D -h /var/md2html -u 1000 md2html
USER md2html
WORKDIR /var/md2html
RUN python -m venv venv
RUN --mount=type=cache,target=/var/md2html/.cache/pip,uid=1000,gid=1000 --mount=type=cache,ro,from=build,source=/home/luser/md2html/dist,target=/dist venv/bin/pip install /dist/*.whl
COPY --chown=md2html:users conf/uwsgi.ini /var/md2html/

VOLUME /srv/http
WORKDIR /srv/http
ENTRYPOINT ["uwsgi"]
EXPOSE 1910/tcp
EXPOSE 1910/udp
CMD [ "--ini", "/var/md2html/uwsgi.ini" ]


