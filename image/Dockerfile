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
RUN  pip install /app/*.whl

# Add requirements
ADD requirements.txt /app/requirements.txt
RUN pip install -f https://download.pytorch.org/whl/torch_stable.html -r /app/requirements.txt && \
    rm -rf ~/.cache

# Add languages
RUN export DEBIAN_FRONTEND=noninterative && \
    apt update -q && \
    apt install -y hunspell hunspell-es hunspell-en-us hunspell-de-de hunspell-fr hunspell-it \
        myspell-pt \
        hunspell-gl hunspell-ca && \
    apt clean

# Add application
ADD sentiment.py /app/sentiment.py

# Boot application
ENV LC_ALL=C.UTF-8
WORKDIR /app
CMD gunicorn --bind 0.0.0.0:${MODEL_PORT:-3000} sentiment:app -t 120 \
             --access-logfile - --error-logfile -
