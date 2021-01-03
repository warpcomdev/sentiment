# Customer experience vertical

Este repositorio contiene varias construcciones para realizar analítica de redes sociales. Consiste en los siguientes componentes:

- El directorio [docker/sentiment](docker/sentiment) contiene el código de una aplicación reutilizable que realiza el procesado de texto para **extracción de términos** y **análisis de sentimiento**, encapsulada en forma de imagen Docker.

- El directorio [docker/youtube](docker/youtube) contiene el código de una página de login utilizada para que el cliente final inicie sesión en Youtube, y genere el token que las aplicaciones analíticas utilizan para acceder a su API y recopilar información.

- El directorio [docker/facebook](docker/facebook) contiene el código de una página de login utilizada para que el cliente final inicie sesión en Fcebook, y genere el token que las aplicaciones analíticas utilizan para acceder a su API y recopilar información.

- El directorio [helm/sentiment](helm/sentiment) contiene una tabla Helm para efectuar el **despliegue** de la imagen [docker/sentiment](docker/sentiment) en un cluster **Kubernetes**.

- El directorio [helm/login](helm/login) contiene una tabla Helm para efectuar el **despliegue** de las páginas de login en redes sociales ([facebook](docker/facebook), [youtube](docker/youtube)) en un cluster **Kubernetes**.

- El directorio [etls](etls) (obsoleto) contiene las versiones iniciales de los scripts de **extracción de datos de redes sociales**. Estos scripts han sido movidos a la vertical de Social Networks de urbo.
