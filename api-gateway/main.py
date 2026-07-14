import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

REGISTRO_SERVICIOS_URL = os.environ.get("REGISTRO_SERVICIOS_URL", "http://registro-servicios:8500")

# Lista separada por comas, ej: "https://llega-ya-fronted-eosin.vercel.app,http://localhost:4200"
CORS_ALLOWED_ORIGINS = [
    origen.strip()
    for origen in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:4200"
    ).split(",")
    if origen.strip()
]

app = FastAPI(title="API Gateway", version="1.0.0")

# CORSMiddleware intercepta y responde el preflight OPTIONS automáticamente,
# antes de que llegue a la ruta proxy() -- por eso no era necesario agregar
# "OPTIONS" a la lista de métodos de @app.api_route.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUTAS = {
    "usuarios": "servicio-usuarios",
    "negocios": "servicio-negocios",
    "productos": "servicio-productos",
    "pedidos": "servicio-pedidos",
    "repartidores": "servicio-repartidores",
}

CLIENTE_HTTP = httpx.AsyncClient(timeout=10.0)

HEADERS_EXCLUIDOS = {"host", "content-length", "connection"}


async def _resolver_instancia(nombre_servicio: str) -> dict | None:
    try:
        resp = await CLIENTE_HTTP.get(f"{REGISTRO_SERVICIOS_URL}/registro/servicios/{nombre_servicio}")
        if resp.status_code != 200:
            return None
        instancias = resp.json()
        return instancias[0] if instancias else None
    except httpx.HTTPError:
        return None


@app.api_route("/api/{prefijo}/{resto_ruta:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(prefijo: str, resto_ruta: str, request: Request):
    nombre_servicio = RUTAS.get(prefijo)
    if nombre_servicio is None:
        return JSONResponse(status_code=404, content={"detail": f"ruta desconocida: /api/{prefijo}/"})

    instancia = await _resolver_instancia(nombre_servicio)
    if instancia is None:
        return JSONResponse(status_code=503, content={"detail": f"{nombre_servicio} no disponible"})

    destino = f"http://{instancia['host']}:{instancia['puerto']}/api/{prefijo}/{resto_ruta}"
    if request.url.query:
        destino = f"{destino}?{request.url.query}"

    headers = {k: v for k, v in request.headers.items() if k.lower() not in HEADERS_EXCLUIDOS}
    cuerpo = await request.body()

    try:
        resp = await CLIENTE_HTTP.request(
            request.method, destino, headers=headers, content=cuerpo, cookies=request.cookies
        )
    except httpx.HTTPError:
        return JSONResponse(status_code=502, content={"detail": f"error contactando {nombre_servicio}"})

    respuesta_headers = {
        k: v for k, v in resp.headers.items() if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}
    }
    return Response(content=resp.content, status_code=resp.status_code, headers=respuesta_headers)


@app.get("/gateway/servicios")
async def servicios():
    try:
        resp = await CLIENTE_HTTP.get(f"{REGISTRO_SERVICIOS_URL}/registro/servicios")
        return resp.json()
    except httpx.HTTPError:
        return JSONResponse(status_code=503, content={"detail": "registro-servicios no disponible"})


@app.get("/salud")
def salud():
    return {"status": "ok", "servicio": "api-gateway"}
