# -*- coding: utf-8 -*-
# pylint: disable=missing-function-docstring,missing-module-docstring,invalid-name

import sys
import os
import base64
import json
import xdrlib
from typing import Any, Optional
import requests
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import dotenv
import flask
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto import Random
from werkzeug.middleware.proxy_fix import ProxyFix

# CONFIGURATION SECTION
# ---------------------

from dotenv import load_dotenv
load_dotenv(verbose=True)

def fromjson(path: str) -> str:
    """Read json object from file"""
    with open(path, "r", encoding='utf-8') as jsonfile:
        return json.load(jsonfile)


# Path to client_secret.json and api_secret.json.
#
# client_secret.json is provided by google developer SDK.
# api_secret.json contains an 'ApiParams' object.
CLIENT_SECRET_PATH = os.environ.get("SECRET_PATH",
                                    "secrets") + "/client_secret.json"

SERVICE_NAME = os.environ.get("SERVICE_NAME", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
API_VERSION = os.environ.get("API_VERSION", "v1")
API_SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/yt-analytics.readonly'
]

# SECRET MANAGEMENT SECTION
# -------------------------


def derive_key(password: str,
               salt: Optional[bytes] = None,
               salt_bytes: int = 32,
               dk_len: int = 32) -> (bytes, bytes):
    """Derive encryption key from given password"""
    if salt is None:
        salt = Random.new().read(salt_bytes)
    return (salt, PBKDF2(password.encode('utf-8'), salt, dk_len))


def encrypt(secret: str, data: Any, nonce_bytes: int = 16) -> str:
    """Serialize and encrypt an object"""
    nonce = Random.new().read(nonce_bytes)
    salt, key = derive_key(secret)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = json.dumps(data).encode('utf-8')
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    packer = xdrlib.Packer()
    packer.pack_bytes(salt)
    packer.pack_bytes(nonce)
    packer.pack_bytes(tag)
    packer.pack_bytes(ciphertext)
    return base64.standard_b64encode(packer.get_buffer()).decode('utf-8')


def decrypt(secret: str, cipherstr: str) -> Any:
    """Deserializes and decrypts object"""
    unpacker = xdrlib.Unpacker(
        base64.standard_b64decode(cipherstr.encode('utf-8')))
    salt = unpacker.unpack_bytes()
    nonce = unpacker.unpack_bytes()
    tag = unpacker.unpack_bytes()
    ciphertext = unpacker.unpack_bytes()
    salt, key = derive_key(secret, salt=salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return json.loads(plaintext.decode('utf-8'))


def chunks(string: str, length: int = 60):
    """Split a string into chunks of fixed size"""
    return tuple(string[0 + i:length + i]
                 for i in range(0, len(string), length))


# APPLICATION SECTION
# -------------------

app = flask.Flask(__name__)
app.secret_key = Random.get_random_bytes(32)
# Add support for prefix-based proxy, in case we deploy as serverless
app.wsgi_app = ProxyFix(app.wsgi_app,
                        x_proto=1,
                        x_host=1,
                        x_port=1,
                        x_prefix=1)


@app.route('/')
def index():
    return flask.render_template('index.html', status='')


@app.route('/static/<path:path>')
def send_static(path: str):
    """Render static content"""
    return flask.send_from_directory('static', path)


@app.route('/test')
def test():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    service = googleapiclient.discovery.build(SERVICE_NAME,
                                              API_VERSION,
                                              credentials=credentials,
                                              cache_discovery=False)

    plaintext = {
        "credentials": flask.session['credentials'],
        "methods": [k for k in dir(service) if not k.startswith("_")]
    }

    status = """
    <h2>Credenciales obtenidas con éxito!</h2>
    <p>Por favor envíe el siguiente texto a soporte:</p>
    <pre>%s</pre>
    """ % "\n".join(chunks(encrypt(SECRET_KEY, plaintext)))
    return flask.render_template('index.html', status=status)


@app.route('/authorize')
def authorize():
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = google_auth_oauthlib.flow.Flow.from_client_config(CLIENT_SECRET,
                                                             scopes=API_SCOPES)

    # The URI created here must exactly match one of the authorized redirect URIs
    # for the OAuth 2.0 client, which you configured in the API Console. If this
    # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
    # error.
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    flask.session['state'] = state

    return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = flask.session['state']

    flow = google_auth_oauthlib.flow.Flow.from_client_config(CLIENT_SECRET,
                                                             scopes=API_SCOPES,
                                                             state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    credentials = flow.credentials
    flask.session['credentials'] = credentials_to_dict(credentials)

    return flask.redirect(flask.url_for('test'))


@app.route('/revoke')
def revoke():
    if 'credentials' not in flask.session:
        status = """Debe <a href="authorize">autorizar</a> el acceso a la
                 aplicación, antes de revocar las credenciales."""
        return flask.render_template('index.html', status=status)

    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    result = requests.post(
        'https://oauth2.googleapis.com/revoke',
        params={'token': credentials.token},
        headers={'content-type': 'application/x-www-form-urlencoded'})

    status_code = getattr(result, 'status_code')
    if status_code == 200:
        return flask.render_template(
            'index.html', status='Credenciales revocadas con éxito.')
    return flask.render_template(
        'index.html',
        status='Se ha producido un error revocando las credenciales.')


@app.route('/clear')
def clear():
    if 'credentials' in flask.session:
        del flask.session['credentials']
    return flask.render_template('index.html', status='Sesión cerrada.')


def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

if __name__ == "__main__":
    CIPHERSTR = ''.join(sys.argv[1].split())
    print(json.dumps(decrypt(SECRET_KEY, CIPHERSTR), indent=2))
else:
    CLIENT_SECRET = fromjson(CLIENT_SECRET_PATH)
