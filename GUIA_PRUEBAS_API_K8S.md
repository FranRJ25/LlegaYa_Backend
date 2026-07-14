# Guía de pruebas — LlegaYa API en Kubernetes local

Esta guía documenta el flujo completo y verificado para levantar el cluster
y probar los endpoints que **sí funcionan**, tal como se corrieron en las
pruebas locales.

---

## 1. Requisitos previos (una sola vez)

Antes de esto, ya deben estar aplicados en el cluster:

```powershell
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/redis/
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/mongo/
kubectl apply -f k8s/sqlserver/
kubectl apply -f k8s/registro-servicios/
kubectl apply -f k8s/config-server/
kubectl apply -f k8s/api-gateway/
kubectl apply -f k8s/servicio-usuarios/ -f k8s/servicio-negocios/ -f k8s/servicio-productos/ -f k8s/servicio-pedidos/ -f k8s/servicio-repartidores/
```

Estos comandos **no se repiten** cada sesión — quedan grabados en el cluster.
Solo se vuelven a correr si se edita algún manifiesto YAML.

---

## 2. Encender el entorno (cada sesión de trabajo)

### 2.1 Docker Desktop
Abrir Docker Desktop y esperar a que el ícono de Kubernetes quede **verde**.

### 2.2 Verificar que los pods sigan vivos

```powershell
kubectl get pods -n llegaya
```

Todos deben decir `Running`. Si es así, los datos y despliegues previos
siguen intactos.

---

## 3. Abrir los port-forwards (cada sesión de trabajo)

Los `port-forward` son túneles temporales: viven únicamente mientras la
terminal donde se ejecutaron sigue abierta. Hay que abrir **una terminal
de PowerShell por cada uno**, y dejarlas corriendo sin cerrar.

| Servicio | Comando | Puerto local |
|---|---|---|
| API Gateway | `kubectl port-forward -n llegaya svc/api-gateway 9000:8080` | `9000` |
| Postgres (usuarios/negocios/productos) | `kubectl port-forward -n llegaya svc/postgres 5434:5432` | `5434` |
| SQL Server (pedidos) | `kubectl port-forward -n llegaya svc/sqlserver 14330:1433` | `14330` |
| MongoDB (repartidores) | `kubectl port-forward -n llegaya svc/mongo 27019:27017` | `27019` |

> El puerto de la **izquierda** es el que tú eliges (puede cambiar).
> El puerto de la **derecha** es el del `Service` dentro del cluster (no se toca).

### Verificación rápida de que el Gateway responde:

```powershell
Invoke-RestMethod http://localhost:9000/gateway/servicios | ConvertTo-Json -Depth 5
```

Debe devolver las 5 claves de microservicios registrados
(`servicio-usuarios`, `servicio-negocios`, `servicio-productos`,
`servicio-pedidos`, `servicio-repartidores`).

---

## 4. Flujo de pruebas de API (verificado end-to-end)

Todas las rutas van con base `http://localhost:9000` (o el puerto que
hayas elegido para el port-forward del gateway).

### 4.1 Registrar cliente

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:9000/api/usuarios/register/ `
  -ContentType "application/json" `
  -Body (@{email="cliente1@test.com"; password="Clave1234"; nombre="Ana"; apellido="Perez"; telefono="912345678"; rol="cliente"} | ConvertTo-Json)
```

### 4.2 Registrar negocio (usuario con rol admin)

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:9000/api/usuarios/register/ `
  -ContentType "application/json" `
  -Body (@{email="negocio1@test.com"; password="Clave1234"; nombre="Luis"; rol="admin"} | ConvertTo-Json)
```

### 4.3 Login del negocio y guardar el token

```powershell
$loginNegocio = Invoke-RestMethod -Method Post -Uri http://localhost:9000/api/usuarios/login/ `
  -ContentType "application/json" `
  -Body (@{email="negocio1@test.com"; password="Clave1234"} | ConvertTo-Json)
$headersNegocio = @{ Authorization = "Bearer $($loginNegocio.access)" }
```

### 4.4 Crear el negocio

```powershell
$negocio = Invoke-RestMethod -Method Post -Uri http://localhost:9000/api/negocios/mi-negocio/ `
  -Headers $headersNegocio -ContentType "application/json" `
  -Body (@{nombre="Bodega Ana"; direccion="Av. Siempre Viva 123"; categoria="bodega"; ruc="12345678901"} | ConvertTo-Json)
$negocioId = $negocio.id
$negocioId
```

### 4.5 Crear producto

```powershell
$producto = Invoke-RestMethod -Method Post -Uri http://localhost:9000/api/productos/crear/ `
  -Headers $headersNegocio -ContentType "application/json" `
  -Body (@{negocio_id=$negocioId; nombre="Chaufa"; precio="18.50"; categoria="comida"} | ConvertTo-Json)
$productoId = $producto.id
$productoId
```

### 4.6 Login del cliente

```powershell
$loginCliente = Invoke-RestMethod -Method Post -Uri http://localhost:9000/api/usuarios/login/ `
  -ContentType "application/json" `
  -Body (@{email="cliente1@test.com"; password="Clave1234"} | ConvertTo-Json)
$headersCliente = @{ Authorization = "Bearer $($loginCliente.access)" }
```

### 4.7 Crear pedido

```powershell
$pedido = Invoke-RestMethod -Method Post -Uri http://localhost:9000/api/pedidos/crear/ `
  -Headers $headersCliente -ContentType "application/json" `
  -Body (@{direccion_entrega="Av. Siempre Viva 123"; items=@(@{producto_id=$productoId; cantidad=2})} | ConvertTo-Json -Depth 5)
$pedidoId = $pedido[0].id
$pedidoId
```

### 4.8 Registrar y loguear repartidor

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:9000/api/usuarios/register/ `
  -ContentType "application/json" `
  -Body (@{email="repartidor1@test.com"; password="Clave1234"; nombre="Pedro"; rol="repartidor"} | ConvertTo-Json)

$loginRepartidor = Invoke-RestMethod -Method Post -Uri http://localhost:9000/api/usuarios/login/ `
  -ContentType "application/json" `
  -Body (@{email="repartidor1@test.com"; password="Clave1234"} | ConvertTo-Json)
$headersRepartidor = @{ Authorization = "Bearer $($loginRepartidor.access)" }
```

### 4.9 Crear perfil de repartidor

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:9000/api/repartidores/perfil/ `
  -Headers $headersRepartidor -ContentType "application/json" `
  -Body (@{dni="87654321"; vehiculo="moto"; zona_cobertura="Siempre Viva"} | ConvertTo-Json)
```

### 4.10 Ver pedidos disponibles y tomar el pedido

```powershell
Invoke-RestMethod -Uri http://localhost:9000/api/repartidores/pedidos-disponibles/ -Headers $headersRepartidor

Invoke-RestMethod -Method Post -Uri "http://localhost:9000/api/repartidores/pedidos/$pedidoId/tomar/" -Headers $headersRepartidor
```

**Resultado esperado:** la respuesta trae `"estado": "confirmado"` con
`repartidor_id` asignado. Esto confirma el flujo completo: Gateway → 5
microservicios en Kubernetes → Postgres / SQL Server / MongoDB en el
cluster, funcionando de punta a punta.

---

## 5. Verificar los datos directo en cada base (sin depender de un cliente gráfico)

Útil para confirmar que los datos realmente llegaron a cada motor, sin
depender de que DBeaver/Compass estén bien conectados.

```powershell
# Postgres - usuarios
kubectl exec -n llegaya deploy/postgres -- psql -U llegaya -d usuarios_db -c "SELECT id, email FROM usuario;"

# SQL Server - pedidos (reemplazar TU_PASSWORD por la de k8s/secrets.yaml)
kubectl exec -n llegaya deploy/sqlserver -- /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "TU_PASSWORD" -C -d pedidos_db -Q "SELECT * FROM pedido;"

# MongoDB - repartidores
kubectl exec -n llegaya deploy/mongo -- mongosh repartidores_db --eval "db.getCollectionNames()"
```

---

## 6. Conectar clientes gráficos (DBeaver / Compass)

Con los port-forwards de la sección 3 abiertos:

| Motor | Host | Puerto | Usuario | Base(s) |
|---|---|---|---|---|
| Postgres | `localhost` | `5434` | `llegaya` / pass `llegaya` | `usuarios_db`, `negocios_db`, `productos_db` |
| SQL Server | `localhost` | `14330` | `sa` / pass en `k8s/secrets.yaml` | `pedidos_db` |
| MongoDB | `localhost` | `27019` | — | `repartidores_db` |

> SSMS y Azure Data Studio (retirado desde feb 2026) suelen fallar con el
> certificado autofirmado dentro del túnel de `port-forward`. **DBeaver**
> es el cliente que funcionó de forma confiable en las pruebas.

---

## 7. Errores comunes y solución rápida

| Síntoma | Causa más probable | Solución |
|---|---|---|
| `No es posible conectar con el servidor remoto` | El port-forward no está corriendo, o se usó el puerto equivocado | Verificar con `Test-NetConnection -ComputerName localhost -Port <puerto>` |
| `Connection refused` en DBeaver/Compass | Terminal del port-forward se cerró | Reabrir el `kubectl port-forward` correspondiente |
| Bases de datos "vacías" al conectar | Se está viendo la conexión vieja de Docker Compose (otro puerto) en vez de la de Kubernetes | Confirmar el puerto de la conexión en el cliente gráfico |
| `Ya existe usuario con este email` | El email ya fue usado en una prueba anterior (dato persistente en el PVC) | Usar un email distinto |
| `405 Method Not Allowed` en el navegador (preflight OPTIONS) | CORS no configurado en el Gateway | Ver fix aplicado en `api-gateway/main.py` (CORSMiddleware) |

---

## 8. Apagar (opcional)

Los pods y datos persisten aunque cierres todo. Solo hace falta cerrar las
terminales de `port-forward` cuando termines de trabajar — no es necesario
borrar nada del cluster entre sesiones.
