# Customer experience vertical

Este repositorio contiene varias construcciones para realizar analítica de redes sociales. Consiste en los siguientes componentes:

- El directorio [docker](docker) contiene el código de una aplicación reutilizable que realiza el procesado de texto para **extracción de términos** y **análisis de sentimiento**, encapsulada en forma de imagen Docker.

- El directorio [helm](helm) contiene la tabla [sentiment](helm/sentiment) para efectuar el **despliegue** de la imagen anterior en un cluster **Kubernetes**.

- El directorio [etls](etls) contiene los scripts de **extracción de datos de redes sociales**, que utilizan el servicio de procesado de texto anterior para analizar la información publicada por dichas redes, y almacenan los resultados en base de datos.
