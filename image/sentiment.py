#!/usr/bin/env python
import os
import string
import random

from transformers import AutoTokenizer, TFAutoModelForSequenceClassification
import tensorflow as tf

from flask import Flask, make_response, jsonify, request, abort
from flask_httpauth import HTTPTokenAuth
auth = HTTPTokenAuth(scheme='Bearer')

MODEL_ENV_DIR = os.getenv('MODEL_ENV_DIR', '/etc/sentiment')
from dotenv import load_dotenv
load_dotenv(MODEL_ENV_DIR)


app = Flask(__name__)


def as_boolean(val: str):
    """Turn a string into a boolean"""
    return True if val.lower() in (
        'y', 'yes', 't', 'true', 's', 'si', 'sí', '1', 'o'
    ) else False

MODEL_CACHE_DIR = os.getenv('MODEL_CACHE_DIR', '/var/cache/sentiment')
MODEL_PORT = int(os.getenv('MODEL_PORT', default='3000'))
MODEL_NAME = os.getenv('MODEL_NAME', default='nlptown/bert-base-multilingual-uncased-sentiment')
MODEL_IS_PYTORCH = as_boolean(os.getenv('MODEL_IS_PYTORCH', default='t'))
MODEL_DEBUG = as_boolean(os.getenv('MODEL_DEBUG', default='f'))
MODEL_TOKEN = os.getenv('MODEL_TOKEN', ''.join(random.choices(
    string.ascii_uppercase +
    string.ascii_lowercase +
    string.digits, k=32)))


class Pipeline:

    """Pipeline built with Hugginface's transformers"""

    def __init__(self, model_name, cache_dir=None, from_pt=False):
        """Init the pipeline from the given model name"""
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = TFAutoModelForSequenceClassification.from_pretrained(model_name, cache_dir=cache_dir, from_pt=from_pt)

    def __call__(self, sentences):
        """Apply the pipeline to a list of sentences"""
        tokens = self.tokenizer(sentences, padding=True, truncation=True, return_tensors='tf')
        legits = self.model(tokens)
        result = tf.nn.softmax(legits).numpy()[0]
        return result

pipeline = Pipeline(MODEL_NAME, cache_dir=MODEL_CACHE_DIR, from_pt=MODEL_IS_PYTORCH)


@auth.verify_token
def verify_token(token):
    """Only the MODEL_TOKEN is currently supported"""
    if token == MODEL_TOKEN:
        return 'admin'


@app.route('/healthz')
def healthz():
    """Health endpoint"""
    try:
        pipeline(['Test sentence to trigger the pipeline'])
        return jsonify({'status': 'ok'})
    except:
        return make_reponse(jsonify({'error': 'test failed'}), 500)


@app.route('/api/sentiment', methods=['POST'])
@auth.login_required
def sentiment():
    """Expects a list of strings embedded in JSON { 'sentences': [ ... ] }"""
    if not request.json or not 'sentences' in request.json:
         abort(400)
    sentences = request.json['sentences']
    return jsonify({'sentiment': pipeline(sentences) })


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not Found'}), 404)


@auth.error_handler
def auth_error(status):
    return make_response(jsonify({'error': 'Invalid credentials'}), status)


if __name__ == '__main__':
    print(f"USE BEARER TOKEN '{MODEL_TOKEN}'")
    app.run(port=MODEL_PORT, debug=MODEL_DEBUG)

