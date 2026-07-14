import logging
import threading
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_instance_id = None
_iniciado = False


def _registrar():
    payload = {
        "nombre_servicio": settings.NOMBRE_SERVICIO,
        "host": settings.SERVICIO_HOST,
        "puerto": settings.SERVICIO_PUERTO,
        "health_check_url": f"http://{settings.SERVICIO_HOST}:{settings.SERVICIO_PUERTO}/salud/",
    }
    try:
        resp = requests.post(
            f"{settings.REGISTRO_SERVICIOS_URL}/registro/registrar", json=payload, timeout=5
        )
        resp.raise_for_status()
        instance_id = resp.json()["instance_id"]
        logger.info("%s registrado en registro-servicios (instance_id=%s)", settings.NOMBRE_SERVICIO, instance_id)
        return instance_id
    except requests.RequestException as exc:
        logger.warning("no se pudo registrar %s en registro-servicios: %s", settings.NOMBRE_SERVICIO, exc)
        return None


def _bucle_heartbeat():
    global _instance_id
    while True:
        time.sleep(15)
        if _instance_id is None:
            _instance_id = _registrar()
            continue
        try:
            url = f"{settings.REGISTRO_SERVICIOS_URL}/registro/heartbeat/{settings.NOMBRE_SERVICIO}/{_instance_id}"
            resp = requests.post(url, timeout=5)
            if resp.status_code == 404:
                _instance_id = _registrar()
        except requests.RequestException as exc:
            logger.warning("heartbeat fallido para %s: %s", settings.NOMBRE_SERVICIO, exc)


def iniciar():
    """Registra el servicio y arranca el hilo de heartbeat (cada 15s). Idempotente y best-effort."""
    global _instance_id, _iniciado
    if _iniciado:
        return
    _iniciado = True
    _instance_id = _registrar()
    hilo = threading.Thread(target=_bucle_heartbeat, daemon=True)
    hilo.start()
