# Login Helm chart

Este directorio contiene una tabla Helm para desplegar los portales de login en las diferentes redes sociales (google, facebook, etc), proporcionados por las imagenes docker definidas en [este mismo repositorio](../../docker).

## Prerequisitos

### Dominios

Las URLs que utiliza el cliente final para acceder a las páginas de login, deben estar dadas de alta como orígenes oAuth válidos en las diversas aplicaciones creadas en las redes sociales. Es imprescindible:

- Fijar un nombre de dominio para la web de login de cada servicio (youtube, facebook, etc), por ejemplo:

  - `https://youtube.analytics.<your wildcard DNS name>`
  - `https://facebook.analytics.<your wildcard DNS name>`
  
- Configurar los DNS públicos para que dichos nombres de dominio se dirijan a la dirección IP pública asignada al Ingress de nuestro cluster de Kubernetes.
- Incluir esas URLs como orígenes válidos en las aplicaciones sociales correspondientes, como se indica [aqui](../../docker/README.md)

### Certificados

Para poder publicar las webs de inicio de sesión por HTTPS, con certificados automáticos (de [Let's Encrypt](https://letsencrypt.org)), la tabla requiere que el cluster Kubernetes tenga instalado el [operador de certmanager](https://cert-manager.io/docs/).

En el caso de usar *Let's Encrypt* y el operador *CertManager*, será suficiente con sobrescribir los siguientes parámetros del fichero `values.yaml`:

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

Si no se van a usar certificados de Let's Encrypt, sino algún otro certificado pre-existente, se debe crear un **Secreto Kubernetes** que almacene:

- La clave privada del certificado, en formato PEM,  en la entrada `tls.key`.
- El certificado de la CA raíz, en formato PEM,  en la entrada `ca.crt`.
- La cadena de certficado pública a utilizar, en formato PEM, en la entrada `tls.crt`.

Este secreto puede crearse a partir de los tres ficheros PEM, usando esta orden:

```bash
kubectl create secret generic -n <nombre_del_namespace> <nombre_del_secreto> --from-file=ca.crt --from-file=tls.key --from-file tls.crt
```

El nombre del secreto debe especificarse en la variable `tls.secret` al desplegar la tabla Helm, estableciendo `tls.create` a `False`:

```yaml
tls:
    # True para usar TLS en el ingress
    enabled: True
    # True para crear el objeto Certificate de cert-manager
    create: False
    # Nombre y tipo del issuer configurado con el operador de CertManager
    issuer: ""
    type: ""
    # Nombre del secreto donde se almacenará el certificado,
    # por defecto coincide con el nombre de release Helm.
    secret: "nombre_del_secreto"
```

Por supuesto, en este caso la gestión del ciclo de vida del secreto (caducidad y renovaciones) deberá realizarse manualmente.

### Cuentas

Las aplicaciones sociales requieren típicamente de credenciales de una **cuenta de desarrollador** o de negocio, antes de permitir que se realicen integraciones con sus cuentas de usuario.

Estas credenciales han de ser obtenidas antes de comenzar con el despliegue de esta aplicación.

El tipo de credenciales necesarias, y las instrucciones sobre cómo obtenerlas, está documentado junto con la imagen docker que implementa cada uno de los portales de login:

- [instrucciones para google (youtube, doogle docs, etc)](../../docker/youtube/README.md)
- [instrucciones para facebook (facebook, instagram, etc)](../../docker/facebook/README.md)

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
              "https://youtube.analytics.<your wildcard domain>/oauth2callback",
              "https://localhost:8443/oauth2callback"
          ],
          "javascript_origins": [
              "https://youtube.analytics.<your wilcard domain>",
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
  - "facebook.analytics.<your wildcard domain>"
  youtube:
  - "youtube.analytics.<your wildcard domain"
```

Es muy importante que el primer hostname de la lista para cada red social tenga **menos de 64 caracteres** de longitud (véase https://github.com/jetstack/cert-manager/issues/2794).

### Recursos

Los recursos (memoria y CPU) a asignar al pod se especifican con el parámetro `resources`:

```yaml
resources:
    limits:
        cpu: "150m"
        memory: "128Mi"
    requests:
        cpu: "250m"
        memory: "200Mi"
```
