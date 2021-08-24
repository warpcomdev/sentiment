# Facebook

Esta carpeta contiene la ETL de análisis de datos de twitter.

## Carga de datos

### Métricas

La ETL recopila de la API v2 de Twitter una lista de métricas fija. Las métricas son las siguientes:

- Métricas **públicas** (`public_metrics`) de usuario, descritas en este enlace: https://developer.twitter.com/en/docs/twitter-api/metrics.
- Análisis de tweets obtenidos mediante la API gratuita y abierta de **búsquedas recientes**,  descrita en este enlace: https://developer.twitter.com/en/docs/twitter-api/tweets/search/introduction.

Las APIs públicas están limitadas a información de una semana atrás. La ETL está diseñada para ejecutarse diariamente, y obtener los datos del día anterior.

**Métricas públicas**

Las métricas públicas se obtienen de aquellas cuentas que se hayan enumerado en el fichero [scren_names.csv](screen_names.csv). Para estas cuentas, se obtienen las siguientes métricas:

- `followers_count`: Número acumulado de seguidores de la cuenta en cuestión.
- `following_count`: Número acumulado de otras cuentas a la que la cuenta sigue.
- `tweet_count`: Número acumulado de tweets enviados por la cuenta.
- `id_count`: Número diario de tweets enviados por la cuenta.
- `retweet_count_sum`: Número diario de retweets sobre tweets enviados por la cuenta.
- `reply_count_sum`: Número diario de replies sobre tweets enviados por la cuenta.
- `like_count_sum`: Número diario de likes sobre tweets enviados por la cuenta.
- `quote_count_sum`: Número diario de menciones sobre tweets enviados por la cuenta.

**Métricas obtenidas sobre tweets**

Adicionalmente, la ETL analiza el impacto (sentimiento y numero de likes, retweets y quotes) de todos los mensajes que cumplan una de estas condiciones:

- Son tweets enviados por las cuentas de interés (enumeradas en el fichero [screen_names.csv](screen_names.csv)), o que hacen mención a alguna de dichas cuentas con `@nombre_de_la_cuenta`.
- Son tweets que incluyen alguno de los términos de interés incluidos en el fichero [terms.csv](terms.csv)

Hay que tener en cuenta que al usar la API pública, la ETL tiene estas dos limitaciones:

- El número de resultados puede no ser exhaustivo, twitter puede omitir algunos tweets aunque cumplan las condiciones anteriores.
- El conjunto total de nombres de cuenta y términos de búsqueda se ensamblan formando una `query`, una cadena de caracteres que se envñia a la API de twitter. Esta cadena no puede superar los 512 bytes, por lo que no puede aumentarse arbiatrariamente el número de cuentas de twitter o términos que la ETL puede buscar.

Con estas restricciones, la ETL recupera los tweets que cumplan las condiciones y analiza su polaridad (sentimiento positivo, negativo o neutro) y su impacto (acumulado de likes, replies y retweets), para generar las siguientes métricas:

- `positive_impact`: Impacto de tweets con polaridad positiva.
- `negative_impact`: Impacto de tweets con polaridad negativa.
- `neutral_impact`: Impacto de tweets con polaridad neutra.
- `nps_impact`: Net promoter score, impacto positivo menos impacto negativo.

Adicionalmente, la ETL calcula la frecuencia de términos más usados en los tweets, y extrae los 20 más frecuentes por franja horaria (ignorando todos aquellos términos que aparezcan en el fichero [stopwords.csv](stopwords.csv):

- `top_term:1`: Número de repeticiones del término más usado. 
- `top_term:2`: Número de repeticiones del segundo término más usado. 
- `top_term:3`: Número de repeticiones del tercer término más usado. 
...
- `top_term:20`: Número de repeticiones del vigésimo término más usado. 

### Entidades

Por cada una de las métricas anteriores, la ETL escribe en el Context Broker una entidad de tipo `KeyPerformanceIndicator`, con el valor de cada métrica:

- El `ID` de la entidad `KeyPerformanceIndicator` es el nombre de la métrica.
- El `TimeInstant` coincide con la fecha reportada por Facebook para la métrica.
- El `kpiValue` se establece al valor de la métrica.
- El `source` de la entidad se establece a `twitter`.
- El `product`:
    
  - En el caso de las métricas `top_term:N`, el producto es el término que se repite.

- El `name` y `description` se establecen al nombre y descripción de la métrica.

  - En el caso de las métricas `top_term:N`, el nombre siempre es `top_term`.

La ETL recopila métricas del día anterior.

- Las métricas de usuario son **diarias**. Sólo se crea un `KeyPerformanceIndicator` por día.
- Las métricas de tweet son **horarias**. Se crea un `KeyPerformanceIndicator` por cada hora del día anterior.

## Instalación ETL

### Preparación del entorno

La ETL está escrita en python y requiere de versión 3.7 o superior. Se recomienda instalar todas las dependencias de la ETL en un `virtualenv`, y utilizar dicho `virtualenv` para ejecutarla.

Antes de poder instalar las dependencias, es necesario que el entorno donde se vaya a ejecutar la ETL temga disponibles las librerías de desarrollo de [hunspell](). En ubuntu, estas librerías pueden instalarse con:

```bash
apt install -y hunspell libhunspell-dev \
               hunspell-es hunspell-en-us \
               hunspell-de-de hunspell-fr \
               hunspell-it myspell-pt \
               hunspell-gl hunspell-ca
```

En otras distribuciones, sería necesario buscar e instalar los paquetes equivalentes.

El entorno virtual puede crearse e inicializarse con los comandos:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuración

La ETL obtiene buena parte de su configuración de **variables de entorno**. Las variables de entorno que reconoce son:

- `TWITTER_BEARER_TOKEN`: token de desrrollador de la API de twitter. La documentación sobre la obtención de `bearer tokens` se puede encontrar aquí: https://developer.twitter.com/en/docs/authentication/oauth-2-0/bearer-tokens.
- `KEYSTONE_URL`: URL de conexión al keystone, por ejemplo https://auth.iotplatform.telefonica.com:15001
- `ORION_URL`: URL de conexión a Orion, por ejemplo https://cb.iotplatform.telefonica.com:10026
- `ORION_SERVICE`: Nombre del servicio.
- `ORION_SUBSERVICE`: Nombre del subservicio.
- `ORION_USERNAME`: Usuario de plataforma con permiso para escribir entidades en el servicio y subservicio especificado.
- `ORION_PASSWORD`: Contraseña del usuario especificado.
- `MODEL_NAME`: Nombre del modelo pre-entrenado que se usará para el análisis de sentimiento. La lista de modelos pre-entranados está disponible en https://huggingface.co/models. El `transformer` por defecto es [nlptown/bert-base-multilingual-uncased-sentiment](https://huggingface.co/nlptown/bert-base-multilingual-uncased-sentiment), un modelo BERT entrando para hacer scoring multiidioma en Inglés, Danés, Alemán, Francés, Español e Italiano.
- `MODEL_CACHE`: Ruta al directorio donde se descargará el modelo y se mantendrá su caché. **El modelo es muy grande (del orden de 1GB)**, por lo que se recomienda que este directorio de caché se mantenga entre ejecuciones de la ETL, y no se borre tras cada ejecución.

Estas variables pueden estar definidas en el entorno, o pueden almacenarse en un fichero [.env](sample_env) en el mismo directorio que la ETL.

Además de estas variables de entorno, la ETL utiliza varios **ficheros CSV** para configurar otros aspectos de la ETL:

- [screen_names.csv](screen_names.csv): Lista de cuentas de twitter a recolectar.

```csv
screen_names
mi_usuario_1
mi_usuario_2
...
```

- [terms.csv](terms.csv): Lista de términos de búsqueda en tweets.

```csv
terms
lanzarote
#lanzarote
```

- [mispell.csv](mispell.csv): Lista de correcciones ortográficas a aplicar a los tweets, antes de realizar el análisis de sentimiento. Cada fila de este CSV contiene un código de idioma, una cadena de texto a buscar, y el texto por el que se debe reemplazar.

```csv
lang,wrong,right
es,ke,que
es,ki,qui
es,ze,ce
es,zi,ci
all,covid,Covid
all,lanzarote,Lanzarote
```

El código de idioma `all` provoca que el texto se reemplace en todos los teets, independientemente del idioma que se detecte.

Estas correciones ortográficas también se utilizan en algunos casos para evitar la "lematización" de palabras que no queremos que el analizador sintáctico y de sentimiento procesen. Por ejemplo, por defecto, el analizador sintáctico podría sustituir la palabra `lanzarote` (en minúsculas) por el lema `lanzar`. Para evitar estos errores, se puede sustituir la primera letra de la palabra por una mayúscula (`lanzarote` -> `Lanzarote`), para que el lematizador la trate como un nombre propio.

- [stopwords.csv](stopwords.csv): Lista de términos que no se quieren contar a la hora de confeccionar el top 20 de palabras más repetidas en los tweets. Nótese que no es necesario incluir aquí los `stop words` típicos de cada idioma (como `a`, `de`, `el`, `la`, `los`, `las`...), ya que estos se eliminan automáticamente, junto con cualquier otra palabra de dos o menos caracteres. 

```
csv
stopword
lanzarote
```

### Ejecucion

Una vez disponible el `virtualenv` y el fichero `.env`, la ETL puede ejecutarse con el comando:

```bash
source venv/bin/activate
ETL_CONFIG_PATH=. python collect.py
```

La ETL vuelca información de progreso por la salida estandar y termina con unos de los dos mensajes posibles siguientes:

- "ETL OK" si se ha completado correctamente.
- "ETL KO" si ha habido algún error.


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
