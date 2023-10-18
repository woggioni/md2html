FROM alpine:latest
MAINTAINER Oggioni Walter <oggioni.walter@gmail.com>
RUN apk update
RUN apk add python3 py3-pip uwsgi uwsgi-python3 graphviz uwsgi-gevent3
RUN mkdir /srv/http
RUN mkdir /var/md2html
WORKDIR /var/md2html
RUN python -m venv venv
ADD uwsgi.ini /var/md2html
ADD md2html-*.whl /
RUN venv/bin/pip install /md2html-*.whl && rm /md2html-*.whl
VOLUME /srv/http
WORKDIR /srv/http
ENTRYPOINT ["uwsgi"]
EXPOSE 1910/tcp
EXPOSE 1910/udp
USER nobody
CMD [ "--ini", "/var/md2html/uwsgi.ini" ]


