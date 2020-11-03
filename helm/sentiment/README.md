# Sentiment analysis service

This repository contains a Dockerfile / Helm chart to deploy a sentiment analysis service based on [transformers](https://huggingface.co/transformers/).

## Image

### Supported environment variables

- MODEL_ENV_DIR: Folder containing an `.env` file with further environment parameters. Variables can be read from environment, or from this file. Defaults to `/etc/sentiment`.
- MODEL_CACHE_DIR: Cache folder to store downloaded models (should be a volume). Defaults to `/var/cache/sentiment`.
- MODEL_NAME: Name of the model to download from [hugginface hub](https://huggingface.co/docs) (or path to model stored in volume). Defaults to `nlptown/bert-base-multilingual-uncased-sentiment`.
- MODEL_IS_PYTORCH: Set to `true` if model is pytorch-based (as opposed to tensorflow-based). Defaults to `true`.
- MODEL_PORT: TCP Port to listen at. Defaults to `3000`.
- MODEL_TOKEN: Secret for bearer authentication. Requests are only attended if they include an `Authorization: Bearer` header with this token.

