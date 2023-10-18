#!/bin/bash
set -e

venv/bin/python -m build
mkdir -p docker/build
cp dist/md2html-*.whl docker/build/
cp docker/Dockerfile docker/build/Dockerfile
cp docker/uwsgi.ini docker/build/uwsgi.ini

docker build docker/build --tag alpine:md2html
