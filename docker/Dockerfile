FROM alpine:latest
MAINTAINER Oggioni Walter <oggioni.walter@gmail.com>
#ADD ../dist/md2html-0.2-py3-none-any.whl /
#COPY md2html-*.whl /
ADD md2html-*.whl /
RUN apk update
RUN apk add python3 uwsgi uwsgi-python3
RUN pip3 install /md2html-*.whl && rm /*.whl
RUN mkdir /srv/http
VOLUME /srv/http
WORKDIR /srv/http
ENTRYPOINT ["uwsgi"]
EXPOSE 1180/tcp
EXPOSE 1180/udp
USER nobody
CMD ["--plugin", "/usr/lib/uwsgi/python_plugin.so", "-s", ":1180", "-w", "md2html.uwsgi"]
#RUN useradd luser -s /bin/bash -m -G users

