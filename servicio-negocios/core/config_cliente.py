import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def obtener_config() -> dict:
    """Configuracion adicional no sensible desde el Config Server. Best-effort."""
    try:
        url = f"{settings.CONFIG_SERVER_URL}/config/{settings.NOMBRE_SERVICIO}/{settings.DJANGO_PERFIL}"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json().get("config", {})
    except requests.RequestException as exc:
        logger.warning("no se pudo obtener configuracion de config-server: %s", exc)
        return {}
