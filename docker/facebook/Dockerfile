# syntax = docker/dockerfile:experimental
FROM python:3.8-slim

# Environment and volume
VOLUME /app/secrets
ENV LC_ALL=C.UTF-8

# Add application
RUN mkdir -p /app
ADD requirements.txt /app
RUN pip install -r /app/requirements.txt

WORKDIR /app
ADD static/ /app/static/
ADD templates/ /app/templates/
ADD app.py /app

CMD gunicorn --bind 0.0.0.0:${LOGIN_PORT:-3000} app:app -t 120 \
             --access-logfile - --error-logfile -
