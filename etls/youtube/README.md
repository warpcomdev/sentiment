# Youtube

Esta carpeta contiene la ETL de análisis de datos de youtube.

## Carga de datos

### Métricas

La ETL recopila de la API de *Channel Reports* de Youtube una lista de métricas configurable. La lista de métricas que debe recopilar se enumera en el fichero [reports_metrics.csv](reports_metrics.csv), que contienen en cada fila:

- El nombre del informe (`Report`) (sólo en el caso del fichero `reports_metrics.csv`).
- El nombre de la métrica (`Metric`), es decir, la columna en el informe.
- La descripción (`Description`) dfe la métrica.
- Opcionalmente, una columna de agregación (`Agg`), que se puede utilizar cuando una métrica puede tener asociada alguna dimensión por la que queremos agrupar (por ejemplo, país de origen de las conexiones). Este atributo `Agg` indica la columna del informe por la que se hará la agregación.

El contenido inicial de este fichero se ha generado a partir de dos informes específicos de la API que recopilan una buena parte de la información útil del canal:

- channel_basic_a2, que reporta las estadísitcas básicas del canal (vistas, likes, comentarios, etc)
- channel_demographics_a1, que reporta las vistas del canal segmentadas por grupos demográficos (edad, sexo, etc).

La lista completa de informes disponibles a través de la API de *Channel Reports* de youtube está en https://developers.google.com/youtube/reporting/v1/reports/channel_reports

Si a futuro se añaden o eliminan informes o métricas de la API de Youtube, mientras se mantenga el formato de la API, será suficiente actualizar el listado de métricas para actualizar en consecuencia la lista de `KeyPerformanceIndicator`s importados.

Adicionalmente, la ETL también utiliza un fichero [channel_metrics.csv](channel_metrics.csv) con métricas que no se obtienen de la API de informes, sino de la API de suscripciones. Esta API es más limitada, pero devuelve información agregada útil como:

- Total de vistas.
- Total de suscriptores.
- Total de videos publicados.

La documentación completa de la API de suscripciones se encuentra en https://developers.google.com/youtube/v3/docs/subscriptions/list. El fichero de métricas `channel_metrics.csv` contiene en cada fila:

- El nombre de la métrica de la API de suscripciones (`Metric`).
- La descripción (`Description`).

**channel_metrics.csv**

```csv
Metric,Description
viewCount,Vistas acumuladas en el canal
subscriberCount,suscriptores acumulados en el canal
videoCount,videos publicados en el canal
subscribedCount,Otros canales o los que el canal está suscrito
```

**reports_metrics.csv**

```csv
Report,Metric,Agg,Description
channel_basic_a2,views,country_code,Número de vistas
channel_basic_a2,comments,country_code,Número de comentarios
channel_basic_a2,likes,country_code,Número de likes
channel_basic_a2,dislikes,country_code,Número de dislikes
channel_basic_a2,shares,country_code,Número de shares
channel_basic_a2,watch_time_minutes,country_code,Tiempo de visionado (minutos)
channel_basic_a2,subscribers_gained,country_code,Suscriptores adquiridos
channel_basic_a2,subscribers_lost,country_code,Suscriptores perdidos
channel_basic_a2,videos_added_to_playlists,country_code,Videos añadidos a playlist
channel_basic_a2,videos_removed_from_playlists,country_code,Videos eliminados de playlist
channel_demographics_a1,views_percentage,country_code,Numero de vistas
channel_demographics_a1,views_percentage,subscribed_status,Numero de vistas
channel_demographics_a1,views_percentage,age_group,Numero de vistas
channel_demographics_a1,views_percentage,gender,Numero de vistas
```

### Entidades

Por cada una de las métricas anteriores, la ETL escribe en el Context Broker una entidad de tipo `KeyPerformanceIndicator`, con el valor diario de cada métrica:

- El `ID` de la entidad `KeyPerformanceIndicator` es el nombre de la métrica.
- El `TimeInstant` coincide con la fecha reportada por Youtube para la métrica.
- El `kpiValue` se establece al valor de la métrica.
- El `source` de la entidad se establece a `youtube`.
- El `product` se establece al título del canal cuyas estadísticas se recopilan.
- El `name` y `description` se establecen al nombre y descripción de la métrica.
- Cuando la métrica está segmentada (por ejemplo, idioma del navegador), el campo `aggData` se establece al valor del segmento (`es_ES`, `en_US`, etc). 

La ETL recopila métricas de hasta 3 días atrás, para tolerar cierto número de fallos. Para evitar escribir varias veces en el context broker la misma métrica, la ETL utiliza una entidad de tipo **Bookmark** e ID **youtube**. Estas entidades se usan como marcadores que almacenan en su campo `TimeInstant` la fecha del últimop día cuyas métricas se cargaron en su totalidad. Cada vez que se ejecuta la ETL,

- La ETL obtiene de la API de youtube información de los últimos 3 días.
- La ETL comprueba si existe en el context broker la entidad **Bookmark** con el ID correspondiente.
- Si existe, descarta todos los datos obtenidos de la API previos o de ese día, y solo escribe al Context Broker los datos de días posteriores.
- Si no existe, escribe todos los datos al Context Broker.
- Cada vez que termina con la carga de los datos de un día completo, actualiza la entidad **Bookmark** con la fecha de ese día.

## Instalación ETL

### Preparación del entorno

La ETL está escrita en python y requiere de versión 3.6 o superior. Se recomienda instalar todas las dependencias de la ETL en un `virtualenv`, y utilizar dicho `virtualenv` para ejecutarla. El entorno virtual puede crearse e inicializarse con los comandos:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuración

La ETL de youtube requiere que se proporcione un fichero de credenciales con la siguiente información:

- ID de aplicación de google, creada en el portal de Google Developers.
- Secreto de aplicación de google.
- Token de refresco del propietario del canal
- Scopes de la aplicación:

  - "https://www.googleapis.com/auth/youtube.readonly",
  - "https://www.googleapis.com/auth/yt-analytics.readonly"

- Último token del propietario del canal.
- URL de refresco de tokens: `https://oauth2.googleapis.com/token`.
}

Para obtener toda esta información es necesario crear una aplicación con una cuenta de desarrollador de Google, configurarlas con los permisos adecuados, y hacer que el administrador de los canales a monitorizar inicie sesión en la aplicación, a modo de tester generalmente. El proceso de creación de la cuenta y obtención de credenciales es bastante largo y está descrito [en este README](https://github.com/warpcomdev/sentiment/blob/master/docker/youtube/developer.md).

Una vez con toda la información recopilada, se debe almacenar en un fichero de configuración con este formato:

```json
{
  "client_id": "...",
  "client_secret": "...",
  "refresh_token": "...",
  "scopes": [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly"
  ],
  "token": "...",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

Este fichero puede guardarse con el nombre `credentials.json` en la ruta de la ETL.

La información obtenida de la API de Youtube se almacena en forma de entidades tipo `KeyPerformanceIndicator` en el Context Broker del cliente. La aplicación necesita de las siguientes variables de entorno para conectar al context broker y autenticarse:

- `KEYSTONE_URL`: URL de conexión al keystone, por ejemplo https://auth.iotplatform.telefonica.com:15001
- `ORION_URL`: URL de conexión a Orion, por ejemplo https://cb.iotplatform.telefonica.com:10026
- `ORION_SERVICE`: Nombre del servicio.
- `ORION_SUBSERVICE`: Nombre del subservicio.
- `ORION_USERNAME`: Usuario de plataforma con permiso para escribir entidades en el servicio y subservicio especificado.
- `ORION_PASSWORD`: Contraseña del usuario especificado.

Estas variables pueden estar definidas en el entorno, o pueden almacenarse en un fichero [.env](sample_env) en el mismo directorio que la ETL.

### Ejecucion

Una vez disponible el `virtualenv` y los ficheros de configuración `credentials.json` y `.env`, la ETL puede ejecutarse con el comando:

```bash
source venv/bin/activate
ETL_CONFIG_PATH=. python collect.py credentials.json
```

La ETL vuelca información de progreso por la salida estandar y termina con unos de los dos mensajes posibles siguientes:

- "ETL OK" si se ha completado correctamente.
- "ETL KO" si ha habido algún error.

## Información normativa

### Datos a tratar

La ETL obtiene información de las cuentas de Youtube de un conjunto determinado de usuarios:

- Número de vídeos publicados en los canales del propietario de la cuenta.
- Impacto de dichos videos (visualizaciones, número de comentarios, likes, dislikes).
- Número de suscriptores en los canales del propietario de la cuenta.

Las cuentas de las que se recopila esta información son únicamente aquellas especificadas por el propietario del proyecto. En particular, el propietario de la cuenta debe autorizar la recolección de datos, iniciando sesión en esta URL habilitada a tal efecto: https://youtube.analytics.urbo2.es/

Sólo aceptamos cuentas asociadas a servicios públicos relacionados o directamente gestionados por los contratantes del proyecto. No se recopila información de cuentas personales, organizaciones privadas, u organismos públicos que no tengan relación con los propietarios del proyecto.

### Origen de los datos

Los datos se obtienen a través de la API de Youtube Reporting, documentada aquí: https://developers.google.com/youtube/reporting/v1/reports. Esta API proporciona información anónima, estadística y agregada sobre el impacto de los canales de vídeo de los propietarios de las cuentas autorizadas.

La información accesible a través de la API de reporting es limitada en alcance y duración:

- En lo referente a alcance, la API sólo proporciona valores agregados de visitas, comentarios, likes o dislikes de los vídeos publicados por las cuentas de usuario autorizas.
- En lo referente a duración, la API permite la generación de informes sobre la actividad registrada por las cuentas de usuario en los últimos 6 días. La API retiene los informes generados hasta 60 días.

### Obtención

La obtención de datos se realiza mediante consultas periódicas a la API de Youtube Reporting. Las consultas se realizan diariamente.

### Finalidad

La finalidad de este tratamiento de datos es el cálculo de estadísticas relacionadas con la presencia del propietario del proyecto en la red social youtube, en particular:

- Evolución de su actividad a lo largo del tiempo: número de vídeos publicados, cantidad de suscriptores, número de reacciones (likes, dislikes, comments), etc.

En ningún caso se procesa información de caracter personal.

### Duración

La toma de datos es diaria y se realizará durante tanto tiempo como el propietario del proyecto especifique y proporcione los medios técnicos (alojamiento para la base de datos, capacidad de proceso para las ETLs, etc).

Los datos obtenidos son totalmente anónimos y se retienen indefinidamente.

### Custodia de los datos

Los datos se almacenan en la base de datos especificada por el propietario del proyecto. La responsabilidad de la custodia de dichos datos recae en el propietario de esa base de datos.

## Configuración

La ETL de Youtube requiere que se proporcione un fichero de credenciales que se obtiene (en forma cifrada) iniciando sesión en la URL https://youtube.analytics.urbo2.es/. La ETL necesita que esas credenciales se descifren, para lo cual es necesario utilizar una clave secreta que está custodiada por los responsables de desrrollado de la ETL.

Además de dicho fichero descifrado de claves, la aplicación utiliza varias variables de entorno:

- `POSTGRES_HOST`: Nombre o IP del servidor postgres donde almacenar los datos.
- `POSTGRES_PORT`: Puerto del servidor, por defecto 5432.
- `POSTGRES_DB`: Nombre de la base de datos a usar.
- `POSTGRES_SCHEMA`: Nombre del schema dentro de la base de datos.
- `POSTGRES_USER`: Nombre de usuario para la base de datos.
- `POSTGRES_PASS`: Password del usuario.

Todas estas variables pueden también almacenarse dentro de un fichero `.env`, que será leido por la aplicación antes de comenzar la extracción de datos.
