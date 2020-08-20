#!/usr/bin/env python
import os
import string
import random
import re

from transformers import AutoTokenizer, TFAutoModelForSequenceClassification
import tensorflow as tf

import jsonschema
import hunspell

from flask import Flask, make_response, jsonify, request, abort
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_swagger import swagger
from flask_httpauth import HTTPTokenAuth
from flask_cors import CORS
auth = HTTPTokenAuth(scheme='Bearer')

MODEL_ENV_DIR = os.getenv('MODEL_ENV_DIR', '/etc/sentiment')
from dotenv import load_dotenv
load_dotenv(MODEL_ENV_DIR)


def as_boolean(val: str):
    """Turn a string into a boolean"""
    return True if val.lower() in (
        'y', 'yes', 't', 'true', 's', 'si', 'sí', '1', 'o'
    ) else False

MODEL_PROXY = as_boolean(os.getenv('MODEL_PROXY', default='f'))
MODEL_CACHE_DIR = os.getenv('MODEL_CACHE_DIR', '/var/cache/sentiment')
MODEL_PORT = int(os.getenv('MODEL_PORT', default='3000'))
MODEL_NAME = os.getenv('MODEL_NAME', default='nlptown/bert-base-multilingual-uncased-sentiment')
MODEL_IS_PYTORCH = as_boolean(os.getenv('MODEL_IS_PYTORCH', default='t'))
MODEL_DEBUG = as_boolean(os.getenv('MODEL_DEBUG', default='f'))
MODEL_TOKEN = os.getenv('MODEL_TOKEN', ''.join(random.choices(
    string.ascii_uppercase +
    string.ascii_lowercase +
    string.digits, k=32)))


app = Flask(__name__)
if MODEL_PROXY:
    # Manage X-Forwarded-Proto
    app.wsgi_app = ProxyFix(app.wsgi_app)
CORS(app)


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


class Spellcheck:

    """Spell check pipeline"""
    def __init__(self):
        """Load the hunspell dictionaries"""
        self.lang = {
            'en': hunspell.HunSpell('/usr/share/hunspell/en_US.dic', '/usr/share/hunspell/en_US.aff'),
            'es': hunspell.HunSpell('/usr/share/hunspell/es_ES.dic', '/usr/share/hunspell/es_ES.aff'),
            'de': hunspell.HunSpell('/usr/share/hunspell/de_DE.dic', '/usr/share/hunspell/de_DE.aff'),
            'fr': hunspell.HunSpell('/usr/share/hunspell/fr_FR.dic', '/usr/share/hunspell/fr_FR.aff'),
            'it': hunspell.HunSpell('/usr/share/hunspell/it_IT.dic', '/usr/share/hunspell/it_IT.aff'),
        }

    def __call__(self, sentences):
        """Return spell checked terms"""
        terms = list()

        def check_term(term, checker):
            # Skip uppercased words that can be places, names, etc.
            if term[0].isupper() or checker.spell(term):
                return term
            suggest = checker.suggest(term)
            if len(suggest) > 0:
                return suggest[0]
            return term

        for sentence in sentences:
            lang = sentence['lang']
            text = sentence['text']
            checker = self.lang.get(lang, None)
            if checker is None:
                terms.append(text)
                continue
            tokens = (check_term(term, checker)
                for term in re.findall(r'\w+', text))
            terms.append(' '.join(tokens))
        return terms

spellcheck = Spellcheck()


# Requests schema
schema = {
    'type': 'object',
    'properties': {
        'sentences': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'lang': {'type': 'string'},
                    'text': {'type': 'string'}
                },
                'required': ['lang', 'text']
            }
        }
    },
    'required': ['sentences']
}

def validate(item, schema=schema):
    """Validate item with json schema"""
    try:
        jsonschema.validate(instance=item, schema=schema)
        return True
    except jsonschema.ValidationError as err:
        return False


@auth.verify_token
def verify_token(token):
    """Only the MODEL_TOKEN is currently supported"""
    if token == MODEL_TOKEN:
        return 'admin'


@app.route('/healthz')
def healthz():
    """
    Health endpoint
    ---
    tags:
    - healthz
    responses:
      200:
        description: ok
        schema:
          type: object
          properties:
            status:
              type: string
    """
    return jsonify({'status': 'ok'})


@app.route('/spec')
def spec():
    swag = swagger(app)
    swag['info']['title'] = 'Sentiment Analyzer'
    swag['securityDefinitions'] = {
      'Bearer': {
        'type': 'apiKey',
        'name': 'Authorization',
        'in': 'header',
      }
    }
    swag['host'] = request.host
    swag['schemes'] = [request.scheme]
    return jsonify(swag)


@app.route('/api/sentiment', methods=['POST'])
@auth.login_required
def sentiment():
    """
    Extract sentiment information from sentences
    ---
    tags:
    - sentiment
    parameters:
    - in: body
      name: body
      schema:
        $ref: "#/definitions/sentences"
    security:
    - Bearer: []
    definitions:
    - schema:
        id: sentences
        properties:
          sentences:
            type: array
            description: list of sentences
            items:
              $ref: "#/definitions/sentence"
        required:
        - sentences
    - schema:
        id: sentence
        properties:
          lang:
            type: string
          text:
            type: string
        required:
        - lang
        - text
    - schema:
        id: error
        properties:
          error:
            type: string
        required:
        - error
    responses:
      200:
        description: ok
        schema:
          type: object
          properties:
            sentiment:
              type: array
              items:
                type: array
                items:
                  type: number
      400:
        description: Invalid input
        schema:
          $ref: "#/definitions/error"
      401:
        description: forbidden
        schema:
          $ref: "#/definitions/error"
    """
    if not request.json or not validate(request.json):
        return make_response(jsonify({'error': 'Invalid input'}), 400)
    sentences = tuple(item['text'] for item in request.json['sentences'])
    return jsonify({'sentiment': pipeline(sentences).tolist() })


@app.route('/api/spell', methods=['POST'])
@auth.login_required
def spell():
    """
    Spell check input sentences
    ---
    tags:
    - spelling
    parameters:
    - in: body
      name: body
      schema:
        $ref: "#/definitions/sentences"
    security:
    - Bearer: []
    responses:
      200:
        description: ok
        schema:
          id: spell
          type: object
          properties:
            spell:
              type: array
              items:
                type: string
      400:
        description: Invalid input
        schema:
          $ref: "#/definitions/error"
      401:
        description: forbidden
        schema:
          $ref: "#/definitions/error"
    """
    if not request.json or not validate(request.json):
        return make_response(jsonify({'error': 'Invalid input'}), 400)
    sentences = request.json['sentences']
    return jsonify({'spell': spellcheck(sentences)})


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not Found'}), 404)


@auth.error_handler
def auth_error(status):
    return make_response(jsonify({'error': 'Invalid credentials'}), status)


if __name__ == '__main__':
    print(f"USE BEARER TOKEN '{MODEL_TOKEN}'")
    app.run(host="0.0.0.0", port=MODEL_PORT, debug=MODEL_DEBUG)

