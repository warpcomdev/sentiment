# syntax = docker/dockerfile:experimental
FROM python:3.8-slim

# Environment and volume
VOLUME /app/secrets
ENV LC_ALL=C.UTF-8

# Add application
RUN mkdir /app
ADD requirements.txt /app
RUN --mount=type=cache,target=~/.cache/pip \
    pip install -r /app/requirements.txt

WORKDIR /app
ADD static/ /app/static/
ADD app.py /app

CMD gunicorn --bind 0.0.0.0:${LOGIN_PORT:-3000} app:app -t 120 \
             --access-logfile - --error-logfile -
