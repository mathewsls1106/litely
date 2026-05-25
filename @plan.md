# Plan: Soporte AWS SSM Parameter Store en s3_tui

## Contexto
Agregar soporte para leer configuraciones desde AWS SSM Parameter Store en el paquete `s3_tui`, manteniendo fallback a variables de entorno para funcionar de manera standalone.

## Objetivos
- [ ] Crear clase `SSMConfig` para leer parámetros desde AWS SSM
- [ ] Implementar fallback a variables de entorno cuando SSM no está disponible
- [ ] Integrar `SSMConfig` en la clase `S3Client` existente
- [ ] Exponer configuraciones a boto3 como variables de entorno estándar
- [ ] Mantener backwards compatibility con la API actual de S3Client

## Archivos Afectados
- `/home/pc3/Escritorio/practicas/litely/s3_tui/s3_access.py` - Modificar para agregar soporte SSM

## Pasos Técnicos

### Paso 1: Agregar imports necesarios
Al inicio de `s3_access.py`, agregar:
```python
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError
```

Configurar logger básico:
```python
logger = logging.getLogger(__name__)
```

### Paso 2: Crear clase SSMConfig
Agregar nueva clase después de los imports y antes de `S3Client`:

```python
class SSMConfig:
    """Cliente para leer configuraciones desde AWS SSM Parameter Store."""

    # Nombres de parámetros en SSM
    PARAM_BUCKET_NAME = "/s3_tui/django_aws_storage_bucket_name"
    PARAM_AWS_REGION = "/s3_tui/aws_default_region"

    # Variables de entorno fallback
    ENV_BUCKET_NAME = "DJANGO_AWS_STORAGE_BUCKET_NAME"
    ENV_AWS_REGION = "AWS_DEFAULT_REGION"

    def __init__(self):
        self._ssm_client = None
        self._config_cache = {}

    @property
    def ssm_client(self):
        """Lazy initialization del cliente SSM."""
        if self._ssm_client is None:
            self._ssm_client = boto3.client("ssm")
        return self._ssm_client

    def get_parameter(self, param_name: str, env_var: str, required: bool = False) -> Optional[str]:
        """
        Obtiene un parámetro de SSM con fallback a variable de entorno.

        Args:
            param_name: Nombre del parámetro en SSM
            env_var: Nombre de la variable de entorno fallback
            required: Si es True, lanza ValueError si no se encuentra

        Returns:
            El valor del parámetro o None si no existe y no es requerido
        """
        # Intentar primero desde SSM
        try:
            response = self.ssm_client.get_parameter(
                Name=param_name,
                WithDecryption=True
            )
            value = response.get("Parameter", {}).get("Value")
            if value:
                logger.info(f"Configuración cargada desde SSM: {param_name}")
                return value
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ParameterNotFound":
                logger.debug(f"Parámetro no encontrado en SSM: {param_name}")
            elif error_code in ("AccessDeniedException", "UnauthorizedOperation"):
                logger.warning(f"Sin acceso a SSM: {param_name}")
            else:
                logger.warning(f"Error al leer parámetro de SSM: {e}")
        except Exception as e:
            logger.warning(f"Error de conexión con SSM: {e}")

        # Fallback a variable de entorno
        value = os.environ.get(env_var)
        if value:
            logger.info(f"Configuración cargada desde variable de entorno: {env_var}")
            return value

        # Si es requerido y no se encontró
        if required:
            raise ValueError(
                f"Configuración requerida no encontrada. "
                f"Configure {param_name} en SSM o defina {env_var} como variable de entorno."
            )

        return None

    def get_bucket_name(self) -> str:
        """Obtiene el nombre del bucket S3 (requerido)."""
        return self.get_parameter(
            self.PARAM_BUCKET_NAME,
            self.ENV_BUCKET_NAME,
            required=True
        )

    def get_aws_region(self) -> Optional[str]:
        """Obtiene la región de AWS (opcional)."""
        return self.get_parameter(
            self.PARAM_AWS_REGION,
            self.ENV_AWS_REGION,
            required=False
        )

    @classmethod
    def load_config(cls) -> tuple:
        """
        Carga todas las configuraciones necesarias.

        Returns:
            Tuple (bucket_name, aws_region)
        """
        config = cls()
        bucket_name = config.get_bucket_name()
        aws_region = config.get_aws_region()
        return bucket_name, aws_region
```

### Paso 3: Modificar clase S3Client
Modificar el `__init__` de `S3Client` para usar `SSMConfig`:

```python
class S3Client:
    """Cliente S3 puro para operaciones de almacenamiento."""

    def __init__(self):
        # Cargar configuración desde SSM con fallback a variables de entorno
        ssm_config = SSMConfig()
        self.bucket_name = ssm_config.get_bucket_name()

        # Obtener región y exponerla a boto3
        aws_region = ssm_config.get_aws_region()
        if aws_region:
            os.environ["AWS_DEFAULT_REGION"] = aws_region

        # Inicializar cliente S3
        self.s3 = boto3.client("s3")
```

### Paso 4: Agregar logging básico
Agregar al inicio del archivo (después de imports):
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

## Criterios de Aceptación
1. La clase `SSMConfig` se crea correctamente con lógica de fallback
2. La aplicación funciona con credenciales SSM si están configuradas
3. La aplicación funciona con variables de entorno si SSM no está disponible
4. El bucket name y region se leen correctamente desde SSM
5. `AWS_DEFAULT_REGION` está disponible para boto3 después de cargar config
6. No hay breaking changes en la API existente de S3Client
7. El código maneja errores de manera graceful sin crashear
8. Los mensajes de logging indican correctamente la fuente de configuración

## Notas
- Usar prefijo consistente para parámetros SSM: `/s3_tui/`
- No almacenar credenciales sensibles en código
- Mantener la aplicación standalone (sin dependencia de Django)
- El cliente S3 usa la configuración de forma transparente