import json
import os
import uuid
from datetime import datetime, timezone

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
TTL_SEGUNDOS = int(os.environ.get("REGISTRO_TTL_SEGUNDOS", "30"))

app = FastAPI(title="Registro de Servicios", version="1.0.0")
cliente_redis = redis.from_url(REDIS_URL, decode_responses=True)


class RegistroRequest(BaseModel):
    nombre_servicio: str
    host: str
    puerto: int
    health_check_url: str


class RegistroResponse(BaseModel):
    instance_id: str
    ttl_segundos: int


def _clave(nombre_servicio: str, instance_id: str) -> str:
    return f"registro:{nombre_servicio}:{instance_id}"


def _patron(nombre_servicio: str) -> str:
    return f"registro:{nombre_servicio}:*"


@app.post("/registro/registrar", response_model=RegistroResponse)
def registrar(datos: RegistroRequest):
    instance_id = str(uuid.uuid4())
    valor = {
        "instance_id": instance_id,
        "nombre_servicio": datos.nombre_servicio,
        "host": datos.host,
        "puerto": datos.puerto,
        "health_check_url": datos.health_check_url,
        "registrado_en": datetime.now(timezone.utc).isoformat(),
    }
    cliente_redis.set(_clave(datos.nombre_servicio, instance_id), json.dumps(valor), ex=TTL_SEGUNDOS)
    return RegistroResponse(instance_id=instance_id, ttl_segundos=TTL_SEGUNDOS)


@app.post("/registro/heartbeat/{nombre_servicio}/{instance_id}")
def heartbeat(nombre_servicio: str, instance_id: str):
    clave = _clave(nombre_servicio, instance_id)
    valor = cliente_redis.get(clave)
    if valor is None:
        raise HTTPException(status_code=404, detail="instancia no encontrada, debe volver a registrarse")
    cliente_redis.expire(clave, TTL_SEGUNDOS)
    return {"status": "ok"}


@app.delete("/registro/baja/{nombre_servicio}/{instance_id}")
def baja(nombre_servicio: str, instance_id: str):
    cliente_redis.delete(_clave(nombre_servicio, instance_id))
    return {"status": "ok"}


@app.get("/registro/servicios")
def listar_servicios():
    agrupado: dict[str, list[dict]] = {}
    for clave in cliente_redis.scan_iter(match="registro:*"):
        valor = cliente_redis.get(clave)
        if not valor:
            continue
        instancia = json.loads(valor)
        agrupado.setdefault(instancia["nombre_servicio"], []).append(instancia)
    return agrupado


@app.get("/registro/servicios/{nombre_servicio}")
def listar_instancias(nombre_servicio: str):
    instancias = []
    for clave in cliente_redis.scan_iter(match=_patron(nombre_servicio)):
        valor = cliente_redis.get(clave)
        if valor:
            instancias.append(json.loads(valor))
    if not instancias:
        raise HTTPException(status_code=404, detail=f"no hay instancias vivas de {nombre_servicio}")
    return instancias


@app.get("/salud")
def salud():
    cliente_redis.ping()
    return {"status": "ok", "servicio": "registro-servicios"}
