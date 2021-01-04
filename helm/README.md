# Helm charts

Este directorio contiene las tablas Helm necesarias para proporcionar los servicios auxiliares (análisis de sentimiento, login en redes sociales) que son necesarios para la vertical de Redes Sociales de Urbo.

- [sentiment](sentiment) es la aplicación de análisis de sentimiento, que utilizan las ETLs para asignar un *score* a los comentarios, tweets, etc.
- [login](login) es la aplicación que publica las páginas de login a las diferentes redes sociales (facebook, youtube, etc), para obtener los tokens que luego las ETLs utilizarán para recopilar datos.
