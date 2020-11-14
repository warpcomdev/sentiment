# ETLs

## Modelo de datos

Las interacciones con redes de datos se almacenan en una tabla `cx_engagement` con las siguientes columnas:

- `source`: Origen de los datos (`twitter`, `youtube`, etc.).
- `channel`: Canal al que pertenecen los datos. El concepto de canal depende de la red social. Por ejemplo:

  - En twitter, cada cuenta de usuario se considera un canal.
  - En youtube, se usan los canales de youtube para agregar.

- `day`: Día al que pertenecen las estadísticas.
- `total_followers`: Total de followers / subscribers acumulados hasta ese día.
- `total_followed`: Total de followed acumulados hasta ese día.
- `total_posts`: Total de mensajes / videos / publicaciones hasta ese día

  - En twitter, cada tweet se cuenta como un post.
  - En youtube, cada vídeo es un post.

- `daily_posts`: Mensajes publicados ese día en particular, para los canales en los que esa información está disponible.

  - En youtube, no está disponible.

- `daily_repost`: Número de veces que se han reenviado los mensajes enviados.

  - En twitter: retweets.

- `daily_reply`: Número de respuestas a los mensajes de ese dia concreto.

  - En youtube: comentarios en vídeos.

- `daily_like`: Número de likes a los posts de ese día concreto.
- `daily_quote`: Número de veces que se han mencionado los mensajes de ese día.

Ejemplo de datos:

| source  | channel         | day                 | total_followers | total_followed | total_posts | daily_posts | daily_repost | daily_reply | daily_like | daily_quote |
| ------- | --------------- | ------------------- | --------------- | -------------- | ----------- | ----------- | ------------ | ----------- | ---------- | ----------- |
| twitter | CITTLAN         | 2020-08-24 00:00:00 |             131 |            522 |         165 |             |              |             |            |             |
| twitter | cactlanzarote   | 2020-08-24 00:00:00 |            1892 |            250 |        2284 |             |              |             |            |             |
| twitter | TurismoLZT      | 2020-08-24 00:00:00 |           21990 |           3499 |        9821 |           4 |           14 |           0 |         35 |           3 |
| twitter | LanzaroteESD    | 2020-08-24 00:00:00 |             711 |            285 |        1146 |           1 |           11 |           0 |          0 |           0 |
| twitter | LanzaroteFilm   | 2020-08-24 00:00:00 |             563 |            101 |         223 |             |              |             |            |             |
| twitter | SPEL_TurismoLZT | 2020-08-24 00:00:00 |             470 |            370 |         839 |             |              |             |            |             |
