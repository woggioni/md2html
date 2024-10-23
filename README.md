
## How to

### Build the docker image
```bash
docker build -t gitea.woggioni.net/woggioni/bugis:latest .
```
### Build the pip package
```bash
pyproject-build
```

### Run in docker
```bash
docker run --rm -v /your/document/directory:/srv/http  --user $(id -u):$(id -g) -p 127.0.0.1:8000:8000 gitea.woggioni.net/woggioni/bugis:latest
```

### Run in docker with `nginx` and `plantUML` server

```bash
docker compose up --build
```

