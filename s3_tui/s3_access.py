"""Vertical 1: Capa de Acceso S3 - Lógica pura sin dependencias UI"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

# Cargar variables de entorno desde .env si existe
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


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

    def list_objects(self, prefix=""):
        """Lista objetos en S3 con el prefijo dado."""
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name, Prefix=prefix, Delimiter="/"
            )

            items = []

            # Añadir ".." para directorio padre si no es raíz
            if prefix:
                items.append(
                    {
                        "type": "folder",
                        "name": "..",
                        "key": "/".join(prefix.rstrip("/").split("/")[:-1])
                        + ("/" if "/" in prefix.rstrip("/") else ""),
                        "size": "",
                        "last_modified": "",
                    }
                )

            # Carpetas (CommonPrefixes)
            for p in response.get("CommonPrefixes", []):
                items.append(
                    {
                        "type": "folder",
                        "name": p["Prefix"].split("/")[-2] + "/",
                        "key": p["Prefix"],
                        "size": "",
                        "last_modified": "",
                    }
                )

            # Archivos (Contents)
            for obj in response.get("Contents", []):
                if obj["Key"] == prefix:
                    continue
                items.append(
                    {
                        "type": "file",
                        "name": obj["Key"].split("/")[-1],
                        "key": obj["Key"],
                        "size": self._human_readable_size(obj["Size"]),
                        "last_modified": obj["LastModified"].strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    }
                )

            return items, None
        except Exception as e:
            return [], str(e)

    def upload_file(self, local_path, s3_key):
        """Sube un archivo local a S3."""
        try:
            self.s3.upload_file(local_path, self.bucket_name, s3_key)
            return True, None
        except Exception as e:
            return False, str(e)

    def create_folder(self, prefix, folder_name):
        """Crea una carpeta en S3."""
        try:
            key = f"{prefix}{folder_name.rstrip('/')}/"
            self.s3.put_object(Bucket=self.bucket_name, Key=key)
            return True, None
        except Exception as e:
            return False, str(e)

    def delete_object(self, key):
        """Elimina un objeto de S3."""
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            return True, None
        except Exception as e:
            return False, str(e)

    def download_file(self, key, local_path):
        """Descarga un archivo de S3."""
        try:
            self.s3.download_file(self.bucket_name, key, local_path)
            return True, None
        except Exception as e:
            return False, str(e)

    def _human_readable_size(self, size, decimal_places=2):
        """Convierte bytes a formato legible."""
        for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
            if size < 1024.0 or unit == "PB":
                break
            size /= 1024.0
        return f"{size:.{decimal_places}f} {unit}"