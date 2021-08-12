# Orion API

Este directorio contiene la libreria `orion` para interfaz con el Context Broker de la plataforma Thinking Cities de Telefónica.

El paquete exporta tres clases:

- `FetchError`: contiene toda la información relacionada con el fallo de una petición HTTP al Context Broker o Keystone.
- `Session`: version modificada de `requests.session` que lanza errores tipo `FetchError` cuando hay error, y es thread-safe (almacena una `request.session` por cada thread, en una variable thread-local).
- `ContextBroker`: API del Context Broker.

Instalar con:

```bash
pip install "git+https://github.com/warpcomdev/sentiment#pkg=orion&subdirectory=libs/orion"
```
