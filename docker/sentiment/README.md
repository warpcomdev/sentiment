# Text analysis image

Este directorio contiene el código de la aplicación [sentiment.py](sentiment.py), diseñada para el análisis de texto, la extracción de términos, y el análisis de sentimiento.

Esta aplicación se basa en [BERT (Bidirectional Encoding Representation from Transformers)](https://en.wikipedia.org/wiki/BERT_(language_model)), que en la fecha de desarrollo de esta aplicación representa el estado del arte en el análisis de texto basado en machine learning, desplazando a enfoques previos como Bag of Words o Word Embeddings.

La aplicación utiliza un modelo BERT multilingüe [pre-entrenado con un conjunto de datos de dominio público](https://huggingface.co/nlptown/bert-base-multilingual-uncased-sentiment) que incluye opiniones en 6 idiomas: Inglés, Alemán, Danés, Francés, Español e Italiano. El modelo predice el sentimiento asignando un score entre 1 (muy negativo) y 5 (muy positivo).

La aplicación se distribuye en forma de imagen Docker, incluyendo este directorio el fichero [Dockerfile](Dockerfile) necesario para construirla.

## Construcción

La construcción de la imagen requiere de Docker. Desde este directorio, la imagen puede construirse con:

```bash
docker build --rm -t sentiment:latest .
```

## Ejecución

La aplicación se configura utilizando **variables de entorno**. A continuación se describen las variables de entorno soportadas:

- **MODEL_NAME**: Nombre del modelo a descargar del repositorio https://huggingface.co/models. La aplicación está diseñada para soportar la descarga de distintos modelos, aunque actualmente el valor por defecto y único valor soportado es `nlptown/bert-base-multilingual-uncased-sentiment`.
- **MODEL_CACHE_DIR**: Ruta dentro del contenedor donde almacenar el modelo anterior, una vez descargado. Se recomienda usar un volumen persistente para evitar tener que volver a descargar el modelo cada vez que se arranca el servicio.
- **MODEL_PORT**: Puerto en el que escuchará la API.
- **MODEL_TOKEN**: Token a utilizar para autenticación tipo `Bearer` contra la API.
- **MODEL_PROXY**: Debe establecerse a `true` si la API va a ser publicaa detrás de un proxy inverso.
- **MODEL_DEBUG**: `true` para habilitar el log detallado.

Estas variables deben especificarse al ejecutar el contenedor, por ejemplo:

```bash
docker run --rm -v /opt/sentiment/var:/var/cache/sentiment \
  -e MODEL_NAME=nlptown/bert-base-multilingual-uncased-sentiment \
  -e MODEL_CACHE_DIR=/var/cache/sentiment \
  -e MODEL_PORT=3000 \
  -e MODEL_TOKEN=... \
  -e MODEL_PROXY=false \
  -e MODEL_DEBUG=false \
  -p 3000:3000 \
  sentiment:latest
```

Alternativamente, estas variables pueden almacenarse en un fichero `.env`, y especificar únicamente la ruta a dicho fichero en la variable de entorno `MODEL_ENV_DIR`, por ejemplo:

```bash
cat > /opt/sentiment/etc/.env <<EOF
MODEL_NAME=nlptown/bert-base-multilingual-uncased-sentiment
MODEL_CACHE_DIR=/var/cache/sentiment
MODEL_PORT=3000
MODEL_TOKEN=...
MODEL_PROXY=false
MODEL_DEBUG=false
EOF

docker run --rm -v /opt/sentiment/var:/var/cache/sentiment \
  -v /opt/sentiment/etc:/etc/sentiment:ro \
  -e MODEL_ENV_DIR=/etc/sentiment \
  -p 3000:3000 \
  sentiment:latest
```

En cualquiera de los casos, con estos parámetros, la aplicación descargará el modelo a la ruta `/opt/sentiment` (montada dentro del contenedor en la ruta `/var/cahe/sentiment`), y escuchará peticiones en el puerto 3000.

Las peticiones deberán enviarse con una cabecera `Authorization: Bearer ...` (utilizando el mismo tken que se haya especificado en la variable de entorno `MODEL_TOKEN`).

## API

La aplicación publica su API como documento swagger en la ruta `/spec`. Suponiendo que se ha lanzado la imagen como se describe en la sección anterior, la descripción de la API puede descargarse con el comando:

```bash
curl http://localhost:3000/spec
```

Este documento puede inspeccionarse con cualquier editor que soporte swagger, como https://editor.swagger.io/.

Para facilitar la inspección de la API, el resultado de este comando se ha almacenado en el fichero [api.json](api.json), que puede ser inspeccionado accediendo al enlace [https://petstore.swagger.io/?url=https://raw.githubusercontent.com/warpcomdev/sentiment/master/docker/api.json].
