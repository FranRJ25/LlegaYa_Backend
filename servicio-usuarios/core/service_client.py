import requests
from django.conf import settings


def llamar(metodo: str, ruta: str, headers: dict | None = None, **kwargs):
    """Llama a otro microservicio a través del API Gateway."""
    url = f"{settings.API_GATEWAY_URL}{ruta}"
    return requests.request(
        metodo,
        url,
        headers=headers,
        timeout=5,
        **kwargs,
    )