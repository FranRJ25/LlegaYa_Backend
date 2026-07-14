import os
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException

CONFIG_REPO = Path(os.environ.get("CONFIG_REPO_PATH", "/app/config-repo"))

app = FastAPI(title="Config Server", version="1.0.0")


def _cargar_yaml(nombre_archivo: str) -> dict:
    ruta = CONFIG_REPO / nombre_archivo
    if not ruta.exists():
        return {}
    with ruta.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@app.get("/config/{nombre_servicio}/{perfil}")
def obtener_config(nombre_servicio: str, perfil: str):
    config = {}
    config.update(_cargar_yaml("default.yaml"))
    config.update(_cargar_yaml(f"{nombre_servicio}.yaml"))
    config.update(_cargar_yaml(f"{nombre_servicio}-{perfil}.yaml"))
    if not config:
        raise HTTPException(status_code=404, detail=f"sin configuracion para {nombre_servicio}")
    return {"nombre_servicio": nombre_servicio, "perfil": perfil, "config": config}


@app.get("/salud")
def salud():
    return {"status": "ok", "servicio": "config-server"}
