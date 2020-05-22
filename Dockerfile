FROM python:3.8-slim-buster
COPY . /src
RUN pip --no-cache-dir install /src
