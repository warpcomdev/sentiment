# Twitter

La ETL de Twitter carga el número de interacciones totales y diarias de los usuarios enumerados en el fichero [screen_names.csv](screen_names.csv). Cada línea de ese fichero es un nombre de usuario de twitter, por ejemplo:

```csv
screen_names
mi_usuario_1
mi_usuario_2
...
```

También hace análisis de sentimiento de los tweets que incluyan alguno de los términos incluidos en el fichero [terms.csv](terms-csv).
