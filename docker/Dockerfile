FROM alpine:latest
MAINTAINER Oggioni Walter <oggioni.walter@gmail.com>
RUN apk update
RUN apk add python3 uwsgi uwsgi-python3
RUN mkdir /srv/http
VOLUME /srv/http
WORKDIR /srv/http
ADD md2html-*.whl /
RUN pip3 install /md2html-*.whl && rm /md2html-*.whl
ENTRYPOINT ["uwsgi"]
EXPOSE 1180/tcp
EXPOSE 1180/udp
USER nobody
CMD ["--plugin", "/usr/lib/uwsgi/python_plugin.so", "-s", ":1180", "-w", "md2html.uwsgi"]

