# Login Helm chart

Este directorio contiene una tabla Helm para desplegar los portales de login en las diferentes redes sociales (google, facebook, etc), proporcionados por las imagenes docker definidas en [../docker](../docker).

La tabla requiere que el cluster Kubernetes tenga instalado el [operador de certmanager](https://cert-manager.io/docs/), si se quiere publicar la API por HTTPS.

## Configuración

### Youtube

Los siguientes parámetros definen la configuración de la aplicación de login en youtube:

```yaml
youtube:
  # Secret key to encrypt login token
  secretKey: "xxx...xxx"
  # API secret for youtube login
  clientSecret: |
    {
      "web": {
          "client_id": "xxx...xxx",
          "project_id": "xxx...xxx",
          "auth_uri": "https://accounts.google.com/o/oauth2/auth",
          "token_uri": "https://oauth2.googleapis.com/token",
          "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
          "client_secret": "xxx...xxx",
          "redirect_uris": [
              "https://youtube.analytics.urbo2.es/oauth2callback",
              "https://localhost:8443/oauth2callback"
          ],
          "javascript_origins": [
              "https://youtube.analytics.urbo2.es",
              "https://localhost:8443"
          ]
      }
    }
```

El `clientSecret` se descarga del dashboard de desarrolladores de Google. [este documento](../../docker/youtube/README.md) describe cómo crear un proyecto en el dashboard de google y obtener el `client secret`. 

### Facebook

```yaml
facebook:
  # Secret key to encrypt login token
  secretKey: xxx...xxx
  # Facebook application ID and Secret
  appId: xxx...xxx
  appSecret: xxx...xxx
```

Los valores de `appId` y `appSecret` se obtienen del dashboard de desarrolladores de Facebook. [este documento](../../docker/facebook/README.md) describe cómo crear un proyecto en el dashboard de facebook y obtener sus credenciales. 

## Hostnames

Para que la autenticación oAuth2 contra las distintas redes sociales funcione correctamente, el nombre de dominio en el que se publiquen estos portales debe incluirse en una lista de dominios autorizados, al crear la aplicación en la red social correspondiente.

Por este motivo, el nombre de dominio asignado al ingress de Kubernetes es muy importante en esta tabla. El parámetro `hostnames` enumera los nombres de dominio que se deben asignar a los `Ingress`de cada página de login.

```yaml
# Hostnames for the Kubernetes ingress.
# THE FIRST HOSTNAME MUST BE < 64 CHARACTERS
# SEE https://github.com/jetstack/cert-manager/issues/2794
hostnames:
  facebook:
  - "facebook.analytics.urbo2.es"
  youtube:
  - "youtube.analytics.urbo2.es"
```

Es muy importante que el primer hostname de la lista para cada red social tenga **menos de 64 caracteres** de longitud (véase https://github.com/jetstack/cert-manager/issues/2794).

### Otros parámetros

El resto de variables importantes que pueden configurarse a través de la taba son:

- `port`: Puerto interno en el que escuchará la API (por defecto, 3000).

- `tls`: Configuración para la obtención de certificados, por ejemplo:

```yaml
tls:
    # True para usar TLS en el ingress
    enabled: True
    # True para crear el objeto Certificate de cert-manager
    create: True
    # Nombre y tipo del issuer configurado con el operador de CertManager
    issuer: "letsencrypt-prod"
    type: "ClusterIssuer"
    # Nombre del secreto donde se almacenará el certificado,
    # por defecto coincide con el nombre de release Helm.
    secret: ""
```

- `resources`: Recursos a asignar al pod, por defecto:

```yaml
resources:
    limits:
        cpu: "150m"
        memory: "128Mi"
    requests:
        cpu: "250m"
        memory: "200Mi"
```

El resto de variables soportadas se describen en el fichero [values.yaml](values.yaml), aunque no se recomienda cambiarlas de sus valores por defecto.
