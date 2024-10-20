#!/bin/bash
set -e

venv/bin/python -m build
mkdir -p docker/build
cp dist/bugis-*.whl docker/build/
cp docker/Dockerfile docker/build/Dockerfile

docker build docker/build --tag bugis:latest
