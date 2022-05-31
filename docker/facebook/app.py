#!/usr/bin/env python3
"""Tiny login server to get user's long-lived page tokens"""

import os
import traceback
import base64
import xdrlib
import json
from typing import Optional, Any
from functools import wraps
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto import Random
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
import flask


# DEBUG SECTION
# ---------------------

if os.getenv("DEBUG", "0").strip() == "1":
    import logging
    try: # for Python 3
        from http.client import HTTPConnection
    except ImportError:
        from httplib import HTTPConnection
    HTTPConnection.debuglevel = 1
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


# Configuration section
# ---------------------

FACEBOOK_APPID = os.getenv("FACEBOOK_APPID", "").strip()
FACEBOOK_APPSECRET = os.getenv("FACEBOOK_APPSECRET", "").strip()
FACEBOOK_API_VERSION = os.getenv("FACEBOOK_API_VERSION", "").strip()
SECRET_KEY = os.getenv("SECRET_KEY").strip()

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


def chunks(string: str, length: int):
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


def get_llt(token):
    """Exchanges a regular token for a long-lived one"""
    resp = requests.get(
        f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": FACEBOOK_APPID,
            "client_secret": FACEBOOK_APPSECRET,
            "fb_exchange_token": token
        }).json()
    return resp["access_token"]


def follow_pages(url, token):
    """Follow the pagination for a given url"""
    resp = requests.get(url, params={"access_token": token}).json()
    for page in resp["data"]:
        yield {
            "name": page["name"],
            "id": page["id"],
            "access_token": page["access_token"],
            "_verbose": page,
        }
    if "next" in resp:
        yield from follow_pages(resp["next"], token)


def get_pages(uid, token):
    """Get a list of pages for the given UID"""
    url = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/{uid}/accounts"
    return {
        'user_token': token,
        'pages': tuple(follow_pages(url, token))
    }


# --------------------------------
# Flask functions
# --------------------------------


def as_json(func):
    """Wraps a view returning a dict, to return json"""
    @wraps(func)
    def wrapper():
        resp = flask.Response(json.dumps(func()))
        resp.headers['Content-Type'] = 'application/json; encoding=utf-8'
        return resp

    return wrapper


@app.route("/")
def main():
    """Render the main page"""
    return flask.render_template('index.html', **{
        "appId": FACEBOOK_APPID,
        "apiVersion": FACEBOOK_API_VERSION,
    })


@app.route('/static/<path:path>')
def send_static(path):
    """Render static content"""
    return flask.send_from_directory('static', path)


@app.route("/api/client")
@as_json
def client():
    """Get the client ID and API version"""
    return {
        "appId": FACEBOOK_APPID,
        "apiVersion": FACEBOOK_API_VERSION
    }


@app.route("/api/pages", methods=["POST"])
@as_json
def pages():
    """Get long-lived page tokens for all pages of this customer"""
    user = flask.request.form.get("user")
    token = flask.request.form.get("token")
    info = get_pages(user, get_llt(token))
    return {
        "public": [{ "id": page["id"], "name": page["name"] } for page in info['pages']],
        "secret": encrypt(SECRET_KEY, info),
    }

@app.route('/healthz')
def healthz():
    """Healthz endpoint for Kubernetes"""
    return flask.jsonify({'status': 'ok'})


if __name__ == "__main__":
    # Decrypt message provided as first parameter
    import sys
    if len(sys.argv) <= 1:
        print("You must provide encrypted string", file=sys.stderr)
        sys.exit(-1)
    CIPHERSTR = ''.join(sys.argv[1].split())
    print(json.dumps(decrypt(SECRET_KEY, CIPHERSTR), indent=2))
