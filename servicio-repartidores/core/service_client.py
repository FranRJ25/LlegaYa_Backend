import requests
from django.conf import settings


def llamar(metodo: str, ruta: str, headers: dict | None = None, **kwargs) -> requests.Response:
    """Llama a otro microservicio siempre a traves del API Gateway (nunca directo entre servicios)."""
    url = f"{settings.API_GATEWAY_URL}{ruta}"
    return requests.request(metodo, url, headers=headers, timeout=5, **kwargs)
