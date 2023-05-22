# Run
```bash
uwsgi --plugin /usr/lib/uwsgi/python_plugin.so --http :1180 -w md2html.uwsgi --http-keepalive --http-auto-chunked
```
