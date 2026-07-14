import requests
from django.conf import settings


def llamar(metodo: str, ruta: str, headers: dict | None = None, **kwargs) -> requests.Response:
    """Llama a otro microservicio siempre a traves del API Gateway (nunca directo entre servicios)."""
    url = f"{settings.API_GATEWAY_URL}{ruta}"
    return requests.request(metodo, url, headers=headers, timeout=5, **kwargs)


def obtener_producto(producto_id: int, auth_header: str | None) -> dict | None:
    headers = {"Authorization": auth_header} if auth_header else None
    try:
        resp = llamar("GET", f"/api/productos/{producto_id}/", headers=headers)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None
