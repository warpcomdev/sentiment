# syntax = docker/dockerfile:experimental
# must build with DOCKER_BUILDKIT=1 docker build --rm -t sentiment:latest .
FROM python:3.8-slim

RUN mkdir /app

# Compile requered wheels
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt update -q && \
    apt install -y python3-dev libhunspell-dev build-essential && \
    cd /app && \
    pip wheel hunspell

FROM python:3.8-slim

# install compiled wheels
COPY --from=0 /app/ /app/
RUN --mount=type=cache,target=~/.cache/pip \
    pip install /app/*.whl

# Add requirements
ADD requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=~/.cache/pip \
    pip install -f https://download.pytorch.org/whl/torch_stable.html -r /app/requirements.txt

# Add languages
RUN --mount=type=cache,target=/var/cache/apt --mount=type=cache,target=/var/lib/apt \
    export DEBIAN_FRONTEND=noninterative && \
    apt update -q && \
    apt install -y hunspell hunspell-es hunspell-en-us hunspell-de-de hunspell-fr hunspell-it \
        myspell-pt \
        hunspell-gl hunspell-ca

# Add application
ADD sentiment.py /app/sentiment.py

# Boot application
ENV LC_ALL=C.UTF-8
WORKDIR /app
CMD gunicorn --bind 0.0.0.0:${MODEL_PORT:-3000} sentiment:app -t 120 \
             --access-logfile - --error-logfile -
