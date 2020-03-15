#!/bin/bash
set -e

python3 setup.py bdist_wheel
cp docker/Dockerfile dist/Dockerfile
docker build dist --tag alpine:md2html
