FROM python:3.8-slim

RUN mkdir /app

# Add requirements
ADD requirements.txt /app/requirements.txt
RUN pip install -f https://download.pytorch.org/whl/torch_stable.html -r /app/requirements.txt

# Add application
ADD sentiment.py /app/sentiment.py

# Boot application
WORKDIR /app
CMD gunicorn --bind 0.0.0.0:${MODEL_PORT:-3000} sentiment:app \
             --access-logfile - --error-logfile -
