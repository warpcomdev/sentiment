# Twittter

Esta carpeta contiene la ETL de análisis de datos de twitter.

## Información normativa

### Datos a tratar

La ETL obtiene información de las cuentas de twitter de un conjunto determinado de usuarios:

- Número de tweets posteados por el propietario de la cuenta.
- Impacto de dichos tweets (respuestas, reposts, likes).
- Número de followers de la cuenta.

Las cuentas de las que se recopila esta información son únicamente aquellas especificadas por el propietario del proyecto. En general, sólo aceptamos cuentas asociadas a servicios públicos relacionados o directamente gestionados por los contratantes del proyecto. No se recopila información de cuentas personales, organizaciones privadas, u organismos públicos que no tengan relación con los propietarios del proyecto.

Adicionalmente, esta aplicación recopila el texto de los tweets que mencionan a las cuentas de usuario anteriores, o incluyen alguno de los términos de interés especificados por el propietario del proyecto. La aplicación obtiene sólo el contenido textual de los tweets, para realizar análisis de texto:

- Idioma del mensaje.
- términos incluidos en el mensaje.

No recopila información sobre las cuentas de usuario que escriben dichos tweets.

### Origen de los datos

Los datos se obtienen a través de la API pública de twitter. En concreto, utilizamos la [API v2](https://developer.twitter.com/en/docs/twitter-api/early-access), que en el momento de este desarrollo se encuentra en modo early access, con el objetivo de reemplazar progresivamente a la API v1.

La información accesible a través de la API pública es limitada en alcance y duración:

- En lo referente a alcance, la API pública sólo proporciona los valores actuales de aquellos datos que el usuario ha marcado como abiertos. En paticular, no proporciona datos históricos (por ejemplo, variación del número de followers a lo largo del tiempo)
- En lo referente a duración, la API pública sólo permite la búsqueda de tweets recientes (menos de una semana de antigüedad).

### Obtención

La obtención de datos se realiza mediante consultas periódicas a la API pública v2 de twitter. Las consultas se realizan diariamente.

### Finalidad

La finalidad de este tratamiento de datos es el cálculo de estadísticas relacionadas con la presencia del propietario del proyecto en la red social twitter, en particular:

- Evolución de su actividad a lo largo del tiempo: mensajes enviados por las cuentas relacionadas con el propietario del proyecto, como número de reacciones (likes, reposts, replies), seguidores, etc.

- Análisis anónimo del texto de los tweets relacionados con la actividad del propietario del proyecto: evolución del número de respuestas positivas, negativas o neutras asociadas a ciertos términos.

En ningún caso se procesa información de caracter personal.

### Duración

La toma de datos es diaria y se realizará durante tanto tiempo como el propietario del proyecto especifique y proporcione los medios técnicos (alojamiento para la base de datos, capacidad de proceso para las ETLs, etc).

Los datos obtenidos son totalmente anónimos y se retienen indefinidamente.

### Custodia de los datos

Los datos se almacenan en la base de datos especificada por el propietario del proyecto. La responsabilidad de la custodia de dichos datos recae en el propietario de esa base de datos.

## Configuración

La ETL de Twitter carga el número de interacciones totales y diarias de los usuarios enumerados en el fichero [screen_names.csv](screen_names.csv). Cada línea de ese fichero es un nombre de usuario de twitter, por ejemplo:

```csv
screen_names
mi_usuario_1
mi_usuario_2
...
```

Adicionalmente, la ETL hace una búsqueda de los tweets diarios que hagan referencia a alguna de las cuentas anteriores, así como cualquiera que incluya alguno de los términos especificados en el fichero [terms.csv](terms.csv), por ejemplo:

```csv
terms
lanzarote
#lanzarote
```

Es necesario tener en cuenta que la aplicación usa las cuentas y términos anteriores para construir una consulta que, en la API pública de twitter, no debe exceder los 512 caracteres. Por este motivo, el total de cuentas definidas en `screen_names.csv` y términos en `terms.csv` no debe superar aproximadamente los 300 caracteres.

La ETL necesita un `Bearer token` para consultar la API pública. El token debe estar asociado a una cuenta de desarrollador.

- La documentación sobre la obtención de `bearer tokens` se puede encontrar aquí: https://developer.twitter.com/en/docs/authentication/oauth-2-0/bearer-tokens.
- El bearer token debe epecificarse en la variable de entorno `TWITTER_BEARER_TOKEN`.

Otras variables de entorno que utiliza la aplicación:

- `POSTGRES_HOST`: Nombre o IP del servidor postgres donde almacenar los datos.
- `POSTGRES_PORT`: Puerto del servidor, por defecto 5432.
- `POSTGRES_DB`: Nombre de la base de datos a usar.
- `POSTGRES_SCHEMA`: Nombre del schema dentro de la base de datos.
- `POSTGRES_USER`: Nombre de usuario para la base de datos.
- `POSTGRES_PASS`: Password del usuario.
- `SENTIMENT_URL`: URL de la API del servicio de análisis de sentimiento.
- `SENTIMENT_TOKEN`: Token para autenticación del servicio de análisis de sentimiento.

Todas estas variables pueden también almacenarse dentro de un fichero `.env`, que será leido por la aplicación antes de comenzar la extracción de datos.
