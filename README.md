# Run
```bash
uwsgi --need-plugin /usr/lib/uwsgi/python_plugin.so \
      --need-plugin /usr/lib/uwsgi/gevent_plugin.so \
      -H venv \
      --http :1180 \ 
      -w md2html.uwsgi_handler \ 
      --http-keepalive \
      --http-auto-chunked \ 
      --gevent 10
```

