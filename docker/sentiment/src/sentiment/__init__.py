#!/usr/bin/env python
# pylint: disable=import-error,too-few-public-methods

from sentiment.__main__ import setupApp, Pipeline, Spellcheck, MODEL_CACHE_DIR, MODEL_NAME

if __name__ == "__main__":
    print(f"USE BEARER TOKEN '{MODEL_TOKEN}'")
    app = setupApp()
    app.run(host="0.0.0.0", port=MODEL_PORT, debug=MODEL_DEBUG)

