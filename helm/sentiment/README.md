# Sentiment Helm chart

Este directorio contiene una tabla Helm para desplegar el servicio de análisis de sentimiento proporcionado por la imagen Docker definida en [../../docker/sentiment](../../docker/sentiment).

La imagen requiere que el cluster Kubernetes tenga instalado el [operador de certmanager](https://cert-manager.io/docs/), si se quiere publicar la API por HTTPS.

## Configuración

Las variables que soporta la tabla son:

- `hostnames`: Lista de nombres de dominio publicadas por Kubernetes Ingress. El primer hostname de la lista debe tener **menos de 64 caracteres** de longitud (véase https://github.com/jetstack/cert-manager/issues/2794). Por ejemplo:

```bash
hostnames:
    - "sentiment.<your-wildcard-DNS>"
```

- `port`: Puerto interno en el que escuchará la API (por defecto, 3000).

- `token`: Token de autenticación para proteger las llamadas a la API.

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
        cpu: "4"
        memory: "4Gi"
    requests:
        cpu: "500m"
        memory: "2Gi"
```

El resto de variables soportadas se describen en el fichero [values.yaml](values.yaml), aunque no se recomienda cambiarlas de sus valores por defecto.
