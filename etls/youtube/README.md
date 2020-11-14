# Youtube

Esta carpeta contiene la ETL de análisis de datos de youtube.

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
