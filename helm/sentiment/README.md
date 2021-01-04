# Sentiment Helm chart

Este directorio contiene una tabla Helm para desplegar el servicio de análisis de sentimiento proporcionado por la imagen Docker definida en [../../docker/sentiment](../../docker/sentiment).

## Configuración

### Token de acceso

La API de este servicio puede protegerse reuqiriendo un token de acceso. Actualmente este token es el mismo para todos los clientes del servicio, y se configura con la variable `token`.

```yaml
token: "ThisIsYourBearerTokenKeepItSecret"
```


### Recursos

Los recursos a asignar al pod (memoria, CPU) se especifican con la clave `resources`:

```yaml
resources:
    limits:
        cpu: "4"
        memory: "4Gi"
    requests:
        cpu: "500m"
        memory: "2Gi"
```

### Certificados

Para poder publicar la URL del servicio mediante HTTPS, con certificados automáticos (de [Let's Encrypt](https://letsencrypt.org)), la tabla requiere que el cluster Kubernetes tenga instalado el [operador de certmanager](https://cert-manager.io/docs/).

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

### Nombre de dominio

Si se van a usar certificados, es conveniente fijar el nombre de dominio asignado al servicio, utilizando la variable `hostnames`. 

```bash
hostnames:
    - "sentiment.<your-wildcard-DNS>"
```

Esta variable es realmente una lista de dominios. La única limitación es que el primer hostname de la lista debe tener **menos de 64 caracteres** de longitud (véase https://github.com/jetstack/cert-manager/issues/2794).

### Puerto

Si no se va a publicar la aplicación externamente (porque sólo se va a acceder desde dentro del cluster), es posible que sea conveniente modificar el puerto en el quela aplicación escucha. Esto se controla con la variable `port`:

```yaml
port: 3000
```
