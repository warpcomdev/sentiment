FROM python:3.8-slim

# Environment and volume
VOLUME /app/secrets
ENV LC_ALL=C.UTF-8

# Add application
RUN mkdir /app
ADD requirements.txt app.py static templates /app/
RUN pip install -r /app/requirements.txt

WORKDIR /app
CMD gunicorn --bind 0.0.0.0:${LOGIN_PORT:-3000} app:app -t 120 \
             --access-logfile - --error-logfile -
