# Sentiment docker images

Este directorio contiene las imágenes docker relacionadas con los servicios de anlítica de redes sociales y sentimiento de las verticales de Redes Sociales y Customer Experience de Urbo.

- El directorio [sentiment](sentiment) contiene el código de una aplicación reutilizable que realiza el procesado de texto para **extracción de términos** y **análisis de sentimiento**, encapsulada en forma de imagen Docker.

  La imagen está publicada en dockerhub con el nombre [warpcomdev/sentiment](https://hub.docker.com/r/warpcomdev/sentiment)

- El directorio [youtube](youtube) contiene el código de una página de login utilizada para que el cliente final inicie sesión en Youtube, y genere el token que las aplicaciones analíticas utilizan para acceder a su API y recopilar información.

  La imagen está publicada en dockerhub con el nombre [warpcomdev/youtube-login](https://hub.docker.com/r/warpcomdev/youtube-login)

- El directorio [facebook](facebook) contiene el código de una página de login utilizada para que el cliente final inicie sesión en Fcebook, y genere el token que las aplicaciones analíticas utilizan para acceder a su API y recopilar información.

  La imagen está publicada en dockerhub con el nombre [warpcomdev/facebook-login](https://hub.docker.com/r/warpcomdev/facebook-login)
