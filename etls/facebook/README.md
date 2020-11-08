# Facebook

Esta carpeta contiene la ETL de análisis de datos de facebook.

## Información normativa

### Datos a tratar

La ETL obtiene información de las páginas de Facebook publicadas por un conjunto determinado de usuarios:

- Número de mensajes posteados por el propietario de la página.
- Impacto de dichos posts (respuestas, reacciones, likes...).
- Número de suscriptores de la página.

Las páginas de las que se recopila esta información son únicamente aquellas especificadas por el propietario del proyecto. En particular, el propietario de la cuenta debe autorizar la recolección de datos, iniciando sesión en esta URL habilitada a tal efecto: https://facebook.analytics.urbo2.es/

En general, sólo aceptamos páginas asociadas a servicios públicos relacionados o directamente gestionados por los contratantes del proyecto. No se recopila información de cuentas personales, organizaciones privadas, u organismos públicos que no tengan relación con los propietarios del proyecto.

### Origen de los datos

Los datos se obtienen a través de la API pública de Facebook Page Insights. En concreto, utilizamos la [API v8](https://developers.facebook.com/docs/graph-api/reference/v8.0/insights). Esta API proporciona información anónima, estadística y agregada sobre el impacto social de las páginas publicadas por los propietarios de las cuentas autorizadas.

La información accesible a través de la API pública es limitada en alcance y duración. El siguiente cuadro recoge las limitaciones actualmente publicadas en la página anterior:

![Limitaciones graph API](img/facebook_limitations.png)

### Obtención

La obtención de datos se realiza mediante consultas periódicas a la API de facebook page insights. Las consultas se realizan diariamente.

### Finalidad

La finalidad de este tratamiento de datos es el cálculo de estadísticas relacionadas con la presencia del propietario del proyecto en la red social facebook, en particular:

- Evolución de su actividad a lo largo del tiempo: mensajes publicados en las páginas relacionadas con el propietario del proyecto, número de reacciones (likes, replies, ...), seguidores, etc.

En ningún caso se procesa información de caracter personal.

### Duración

La toma de datos es diaria y se realizará durante tanto tiempo como el propietario del proyecto especifique y proporcione los medios técnicos (alojamiento para la base de datos, capacidad de proceso para las ETLs, etc).

Los datos obtenidos son totalmente anónimos y se retienen indefinidamente.

### Custodia de los datos

Los datos se almacenan en la base de datos especificada por el propietario del proyecto. La responsabilidad de la custodia de dichos datos recae en el propietario de esa base de datos.

## Configuración

La ETL de Facebook requiere que se proporcione un fichero de credenciales que se obtiene (en forma cifrada) iniciando sesión en la URL https://facebook.analytics.urbo2.es/. La ETL necesita que esas credenciales se descifren, para lo cual es necesario utilizar una clave secreta que está custodiada por los responsables de desrrollado de la ETL.

La lista de métricas a recopilar de Facebook se configura en el fichero [metrics.csv](metrics.csv). La lista completa de métricas disponibles se encuentra en la referencia de la API, https://developers.facebook.com/docs/graph-api/reference/v8.0/insights. El fichero `metrics.csv` enumera, para las métricas a recuperar:

- El nombre de la métrica (`Metric`).
- La descripción (`Description`).
- La granularidad de la métrica. La ETL sólo reconoce dos valores posibles:

  - `day`, para métricas que representan datos diarios.
  - `lifetime`, para métricas que representan datos acumulados.

Aunque la API soporta otras granularidades (`week`, `days_28`), la ETL no hace uso de ellas.

Un ejemplo del formato del archivo `metrics.csv`:

```csv
Metric,Description,Granularity
page_views_logged_in_total,The number of times a Page's profile has been viewed by people logged in to Facebook.,day
page_views_logged_in_unique,The number of people logged in to Facebook who have viewed the Page profile.,day
page_views_logout,The number of times a Page's profile has been viewed by people not logged in to Facebook.,day
page_views_total,The number of times a Page's profile has been viewed by logged in and logged out people.,day
post_activity*,The number of stories generated about your Page post ('Stories').,lifetime
```

Además de estos ficheros, la aplicación utiliza varias variables de entorno:

- `POSTGRES_HOST`: Nombre o IP del servidor postgres donde almacenar los datos.
- `POSTGRES_PORT`: Puerto del servidor, por defecto 5432.
- `POSTGRES_DB`: Nombre de la base de datos a usar.
- `POSTGRES_SCHEMA`: Nombre del schema dentro de la base de datos.
- `POSTGRES_USER`: Nombre de usuario para la base de datos.
- `POSTGRES_PASS`: Password del usuario.

Todas estas variables pueden también almacenarse dentro de un fichero `.env`, que será leido por la aplicación antes de comenzar la extracción de datos.
