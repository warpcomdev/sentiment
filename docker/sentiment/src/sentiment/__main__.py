#!/usr/bin/env python
"""Sentiment module performs NLP analysis on text data"""
# pylint: disable=import-error,too-few-public-methods

import os
import string
import random
import json
from collections import Counter
from functools import wraps
from typing import Optional, Iterable, Generator, List, Dict, Callable, TypeVar, Any

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

import jsonschema
import textdistance
import hunspell

import en_core_web_sm
import es_core_news_sm
import de_core_news_sm
import fr_core_news_sm
import it_core_news_sm
import pt_core_news_sm

from dotenv import load_dotenv
from flask import Flask, Response, make_response, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_swagger import swagger
from flask_httpauth import HTTPTokenAuth
from flask_cors import CORS

auth = HTTPTokenAuth(scheme='Bearer')
app = Flask(__name__)
CORS(app)


class Dependencies:
    """Dependency object to consolidate all dependencies"""

    __slots__ = ['token', 'spellcheck', 'pipeline', 'port', 'debug']

    def __init__(self):
        self.token: Optional[str] = None
        self.spellcheck: Optional[Spellcheck] = None
        self.pipeline: Optional[Pipeline] = None
        self.port: Optional[int] = None
        self.debug: Optional[bool] = None


DEPENDENCIES = Dependencies()


def as_boolean(val: str) -> bool:
    """Turn a string into a boolean"""
    return val.lower() in ('y', 'yes', 't', 'true', 's', 'si', 'on', '1')


Rating = Any


class Pipeline:
    """Pipeline built with Hugginface's transformers"""
    def __init__(self, model_name: str, cache_dir: Optional[str] = None):
        """Init the pipeline from the given model name"""
        self.tokenizer = AutoTokenizer.from_pretrained(model_name,
                                                       cache_dir=cache_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name, cache_dir=cache_dir)

    def _batch(self, sentences: List[str]) -> Iterable[Rating]:
        """Analize a batch of sentences"""
        tokens = self.tokenizer(sentences,
                                padding=True,
                                truncation=True,
                                return_tensors='pt')
        logits = self.model(**tokens)[0]
        #pylint: disable=no-member
        result = torch.softmax(logits, dim=1).tolist()
        return result

    def __call__(self,
                 sentences: List[str],
                 batch_size: int = 10) -> Generator[Rating, None, None]:
        """Generate sentiment data for a list of sentences"""
        for index in range(0, len(sentences), batch_size):
            for row in self._batch(sentences[index:index + batch_size]):
                yield row


RT = TypeVar('RT')


def memoize(func: Callable[[str], RT]) -> Callable[[str], RT]:
    """Caching functions of one argument"""
    #pylint: disable=dangerous-default-value
    @wraps(func)
    def wrapped(arg, cache=dict()):
        cached = cache.get(arg, None)
        if cached is None:
            cached = func(arg)
            if cached is not None:
                cache[arg] = cached
        return cached

    return wrapped


NLP = Any


@memoize
def _nlp(spacy_module: str) -> Optional[NLP]:
    print("Loading spacy language model for '", spacy_module, "'")
    if spacy_module == 'en':
        nlp = en_core_web_sm.load()
    elif spacy_module == 'es':
        nlp = es_core_news_sm.load()
    elif spacy_module == 'de':
        nlp = de_core_news_sm.load()
    elif spacy_module == 'fr':
        nlp = fr_core_news_sm.load()
    elif spacy_module == 'it':
        nlp = it_core_news_sm.load()
    elif spacy_module == 'pt':
        nlp = pt_core_news_sm.load()
    else:
        raise ValueError(f'Unsupported language {spacy_module}')
    return nlp


@memoize
def _hunspell(hunspell_file: str) -> hunspell.HunSpell:
    print("Loading hunspell dictionary '", hunspell_file, "'")
    hunspell_folder = '/usr/share/hunspell'
    return hunspell.HunSpell(f'{hunspell_folder}/{hunspell_file}.dic',
                             f'{hunspell_folder}/{hunspell_file}.aff')


Sentence = Dict[str, str] # Two knwon keys: 'lang' and 'text'
TermCount = Dict[str, int]


class Spellcheck:
    """Spell check pipeline"""

    _langs = {
        'en': ['en', 'en_US'],
        'es': ['es', 'es_ES'],
        'de': ['de', 'de_DE'],
        'fr': ['fr', 'fr_FR'],
        'it': ['it', 'it_IT'],
        'pt': ['pt', 'pt_PT'],
        'gl': ['es', 'gl_ES'],
        'ca': ['es', 'ca_ES'],
    }

    @classmethod
    def _tokenizer(cls, lang: str) -> Optional[NLP]:
        """Get the tokenizer for the specified lang"""
        lang_info = cls._langs.get(lang, None)
        if lang_info is None:
            return None
        return _nlp(lang_info[0])

    @classmethod
    def _checker(cls, lang: str) -> Optional[hunspell.HunSpell]:
        """Get the spell checker for the specified lang"""
        lang_info = cls._langs.get(lang, None)
        if lang_info is None:
            return None
        return _hunspell(lang_info[1])

    def __init__(self):
        """Preload all dictionaries to avoid first query delays"""
        for lang in Spellcheck._langs:
            Spellcheck._tokenizer(lang)
            Spellcheck._checker(lang)

    def __call__(
        self, sentences: Iterable[Sentence]
    ) -> Generator[Optional[TermCount], None, None]:
        """Generate spell checked terms"""
        def best_fit(term: str, checker: hunspell.HunSpell) -> str:
            suggest = checker(term)
            if len(suggest) <= 0:
                return term
            for suggestion in suggest[:3]:
                if textdistance.jaro.distance(term, suggestion) <= 2:
                    return suggestion
            return term

        def terms_of(sentence: str, lang: str) -> Optional[TermCount]:
            """Splits sentence into lemmas"""
            # Make sure we support the language
            checker = Spellcheck._checker(lang)
            tokenizer = Spellcheck._tokenizer(lang)
            if checker is None or tokenizer is None:
                return None
            # Remove variation selectors, that confuse the call to isupper()
            # because they are things that modify display of emojis, not actual
            # characters. See:
            # https://en.wikipedia.org/wiki/Variation_Selectors_(Unicode_block)
            sentence = sentence.replace('\ufe0f', '').replace('\ufe0e', '')
            # Lemmatize skipping stop words
            # or short words (<= 2 characters)
            doc = tokenizer(sentence)
            tokens = (token for token in doc if not token.is_stop
                      and not token.is_punct and len(token.norm_) > 2)
            # Do spell checking on lemmas (mispelled words
            # don't have a lemma, they drop through
            # the previous step)
            words = (token.text if
                     (token.text[0].isupper() or checker.spell(token.norm_))
                     else best_fit(token.text, checker.suggest)
                     for token in tokens)
            # Do a second pass to lemmatize corrected words
            doc = tokenizer(' '.join(words))
            words = ((token.text if token.text[0].isupper() else token.lemma_)
                     for token in doc if not token.is_stop
                     and not token.is_punct and len(token.norm_) > 2)
            return dict(Counter(word.lower() for word in words))

        for sentence in sentences:
            text = sentence['text']
            lang = sentence['lang']
            yield terms_of(text, lang)


# Requests schema
schema = {
    'type': 'object',
    'properties': {
        'sentences': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'lang': {
                        'type': 'string'
                    },
                    'text': {
                        'type': 'string'
                    }
                },
                'required': ['lang', 'text']
            }
        }
    },
    'required': ['sentences']
}


#pylint: disable=dangerous-default-value,redefined-outer-name
def validate(item, schema: Any = schema) -> bool:
    """Validate item with json schema"""
    try:
        jsonschema.validate(instance=item, schema=schema)
        return True
    except jsonschema.ValidationError:
        return False


@auth.verify_token
def verify_token(token: str) -> Optional[str]:
    """Only the MODEL_TOKEN is currently supported"""
    if token == DEPENDENCIES.token:
        return 'admin'
    return None


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
    """Return swagger spec for this API"""
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


def make_stream_response(generator: Iterable[Any], fieldname: str) -> Response:
    """Make a streaming response from a generator"""
    def stream(sep=''):
        yield '{"%s":[' % fieldname
        for item in generator:
            yield ''.join((sep, json.dumps(item)))
            sep = ','
        yield ']}'

    return Response(stream(), mimetype='application/json')


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
    return make_stream_response(DEPENDENCIES.pipeline(sentences), 'scores')


@app.route('/api/terms', methods=['POST'])
@auth.login_required
def terms():
    """
    Spell check input sentences
    ---
    tags:
    - terms
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
          id: terms
          type: object
          properties:
            terms:
              type: array
              items:
                type: object
                additionalProperties:
                    type: integer
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
    sentences = tuple(request.json['sentences'])
    return make_stream_response(DEPENDENCIES.spellcheck(sentences), 'terms')


#pylint: disable=unused-argument
@app.errorhandler(404)
def not_found(error):
    """Default 404 handler"""
    return make_response(jsonify({'error': 'Not Found'}), 404)


@auth.error_handler
def auth_error(status):
    """Default error handler"""
    return make_response(jsonify({'error': 'Invalid credentials'}), status)


# pylint: disable=invalid-name
def setupApp():
    """Setup the app dependencies before running"""
    load_dotenv(os.getenv('MODEL_ENV_DIR', '/etc/sentiment'))

    model_proxy = as_boolean(os.getenv('MODEL_PROXY', default='f'))
    model_cache_dir = os.getenv('MODEL_CACHE_DIR', '/var/cache/sentiment')
    model_port = int(os.getenv('MODEL_PORT', default='3000'))
    model_name = os.getenv(
        'MODEL_NAME',
        default='nlptown/bert-base-multilingual-uncased-sentiment')
    model_debug = as_boolean(os.getenv('MODEL_DEBUG', default='f'))
    model_token = os.getenv(
        'MODEL_TOKEN', ''.join(
            random.choices(string.ascii_uppercase + string.ascii_lowercase +
                           string.digits,
                           k=32)))
    if model_proxy:
        # Manage X-Forwarded-Proto
        app.wsgi_app = ProxyFix(app.wsgi_app)

    DEPENDENCIES.pipeline = Pipeline(model_name, cache_dir=model_cache_dir)
    DEPENDENCIES.spellcheck = Spellcheck()
    DEPENDENCIES.token = model_token
    DEPENDENCIES.port = model_port
    DEPENDENCIES.debug = model_debug

    return app


if __name__ == "__main__":
    app = setupApp()
    print(f"USE BEARER TOKEN '{DEPENDENCIES.token}'")
    app.run(host="0.0.0.0", port=DEPENDENCIES.port, debug=DEPENDENCIES.debug)
