FROM python:3.8-slim-buster
RUN pip --no-cache-dir install \
  black \
  flake8 \
  flake8-bugbear \
  inotify_simple \
  isort \
  mypy \
  && pip check
COPY flake8 /root/.config/flake8
COPY isort.cfg /root/.config/isort.cfg
COPY mypy.ini /root/.config/mypy/config
COPY check.py /
