# Guía: levantar y verificar LlegaYa Backend (microservicios)

Comandos en **PowerShell** (Windows). Para bash/git-bash, cambia `Invoke-RestMethod` por `curl` y adapta las comillas.

## 1. Requisitos

- Docker Desktop instalado y **corriendo**.
- Puertos libres: `8001-8005`, `8080`, `8500`, `8600`, `5432`, `6379`, `27017`.

```powershell
docker --version
docker compose version
```

## 2. Variables de entorno (opcional)

Crea un archivo `.env` en la raíz del repo (docker-compose lo lee automáticamente):

```
SECRET_KEY=una-clave-larga-y-aleatoria-para-dev
EMAIL_HOST_USER=tu-correo@gmail.com
EMAIL_HOST_PASSWORD=tu-password-de-aplicacion-gmail
FRONTEND_URL=http://localhost:4200
```

Si no lo creas, todo funciona igual con valores por defecto, excepto el envío real de correos de reset de contraseña.

## 3. Levantar todo

Desde la raíz del repo:

```powershell
docker compose up --build
```

Esto construye y levanta 11 contenedores: `redis`, `postgres`, `mongo`, `registro-servicios`, `config-server`, `api-gateway`, y los 5 `servicio-*`. La primera vez tarda varios minutos.

Deja esa ventana abierta y abre **otra terminal de PowerShell** para verificar.

## 4. Verificar que todo arrancó bien

### 4.1 Contenedores corriendo
```powershell
docker compose ps
```
Todos deben decir `running`. Si alguno no, revisa sus logs:
```powershell
docker compose logs servicio-usuarios --tail=50
```

### 4.2 Los 5 microservicios se registraron en el Registro de Servicios
Espera ~15-20 segundos tras el arranque (el primer heartbeat tarda hasta 15s), luego:
```powershell
Invoke-RestMethod http://localhost:8500/registro/servicios | ConvertTo-Json -Depth 5
```
Debes ver un JSON con las 5 claves: `servicio-usuarios`, `servicio-negocios`, `servicio-productos`, `servicio-pedidos`, `servicio-repartidores`, cada una con al menos una instancia (`host`, `puerto`, `instance_id`).

Si falta alguno, revisa sus logs (`docker compose logs <servicio> --tail=80`) y reinícialo:
```powershell
docker compose restart <servicio>
```

### 4.3 Health checks individuales
```powershell
foreach ($p in 8500,8600,8080) { Invoke-RestMethod "http://localhost:$p/salud" }
foreach ($p in 8001,8002,8003,8004,8005) { Invoke-RestMethod "http://localhost:$p/salud/" }
```
Todos deben responder `status: ok`.

### 4.4 El Gateway ve el registro
```powershell
Invoke-RestMethod http://localhost:8080/gateway/servicios | ConvertTo-Json -Depth 5
```
Debe devolver lo mismo que el paso 4.2.

## 5. Probar el flujo completo de negocio (todo pasa por el Gateway, puerto 8080)

### a) Registrar un cliente
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/usuarios/register/ `
  -ContentType "application/json" `
  -Body (@{email="cliente@test.com"; password="Clave1234"; nombre="Ana"; apellido="Perez"; telefono="912345678"; rol="cliente"} | ConvertTo-Json)
```

### b) Registrar un dueño de negocio
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/usuarios/register/ `
  -ContentType "application/json" `
  -Body (@{email="negocio@test.com"; password="Clave1234"; nombre="Luis"; rol="admin"} | ConvertTo-Json)
```

### c) Login del dueño de negocio y guardar el token
```powershell
$loginNegocio = Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/usuarios/login/ `
  -ContentType "application/json" `
  -Body (@{email="negocio@test.com"; password="Clave1234"} | ConvertTo-Json)
$tokenNegocio = $loginNegocio.access
$headersNegocio = @{ Authorization = "Bearer $tokenNegocio" }
```

### d) Crear el negocio
```powershell
$negocio = Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/negocios/mi-negocio/ `
  -Headers $headersNegocio -ContentType "application/json" `
  -Body (@{nombre="Bodega Ana"; direccion="Av. Siempre Viva 123"; categoria="bodega"; ruc="12345678901"} | ConvertTo-Json)
$negocioId = $negocio.id
```

### e) Crear un producto
Esto valida internamente `servicio-productos` → `servicio-negocios` **vía el Gateway**; si responde 201, confirma que la comunicación entre servicios funciona.
```powershell
$producto = Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/productos/crear/ `
  -Headers $headersNegocio -ContentType "application/json" `
  -Body (@{negocio_id=$negocioId; nombre="Chaufa"; precio="18.50"; categoria="comida"} | ConvertTo-Json)
$productoId = $producto.id
```

### f) Login del cliente y crear un pedido desde el carrito
```powershell
$loginCliente = Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/usuarios/login/ `
  -ContentType "application/json" `
  -Body (@{email="cliente@test.com"; password="Clave1234"} | ConvertTo-Json)
$headersCliente = @{ Authorization = "Bearer $($loginCliente.access)" }

$pedido = Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/pedidos/crear/ `
  -Headers $headersCliente -ContentType "application/json" `
  -Body (@{direccion_entrega="Av. Siempre Viva 123"; items=@(@{producto_id=$productoId; cantidad=2})} | ConvertTo-Json -Depth 5)
$pedidoId = $pedido[0].id
```
`servicio-pedidos` llama a `servicio-productos` (vía Gateway) para validar el producto y calcular el total.

### g) Registrar un repartidor, crear su perfil y tomar el pedido
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/usuarios/register/ `
  -ContentType "application/json" `
  -Body (@{email="repartidor@test.com"; password="Clave1234"; nombre="Pedro"; rol="repartidor"} | ConvertTo-Json)

$loginRepartidor = Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/usuarios/login/ `
  -ContentType "application/json" `
  -Body (@{email="repartidor@test.com"; password="Clave1234"} | ConvertTo-Json)
$headersRepartidor = @{ Authorization = "Bearer $($loginRepartidor.access)" }

Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/repartidores/perfil/ `
  -Headers $headersRepartidor -ContentType "application/json" `
  -Body (@{dni="87654321"; vehiculo="moto"; zona_cobertura="Siempre Viva"} | ConvertTo-Json)

Invoke-RestMethod -Uri http://localhost:8080/api/repartidores/pedidos-disponibles/ -Headers $headersRepartidor
# debe aparecer $pedidoId en la lista

Invoke-RestMethod -Method Post -Uri "http://localhost:8080/api/repartidores/pedidos/$pedidoId/tomar/" -Headers $headersRepartidor
```
Si la respuesta trae `"estado": "confirmado"` y `"repartidor_id"` asignado, **el flujo completo funciona de punta a punta**: Gateway → 5 microservicios → llamadas cruzadas entre ellos → JWT validado sin base de datos compartida.

## 6. Checklist rápido de "todo está bien"

- [ ] `docker compose ps` → todos `running`
- [ ] `/registro/servicios` (puerto 8500) → aparecen los 5 microservicios
- [ ] Los 8 `/salud` responden `ok`
- [ ] Login devuelve `access` + cookie `refresh_token`
- [ ] Negocio → Producto → Pedido → Tomar pedido funciona encadenado (paso 5 completo)
- [ ] Tomar el mismo pedido dos veces da error la segunda vez (código 409)

## 7. Correr los tests automáticos de cada microservicio

Sin Docker (con Python 3.12+ local):
```powershell
cd servicio-usuarios; pip install -r requirements.txt; python manage.py test; cd ..
cd servicio-negocios; pip install -r requirements.txt; python manage.py test; cd ..
cd servicio-productos; pip install -r requirements.txt; python manage.py test; cd ..
cd servicio-pedidos; pip install -r requirements.txt; python manage.py test; cd ..
cd servicio-repartidores; pip install -r requirements.txt; python manage.py test; cd ..
```

Dentro de los contenedores ya corriendo:
```powershell
docker compose exec servicio-usuarios python manage.py test
```

## 8. Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| Un servicio no aparece en `/registro/servicios` | Arrancó antes de que `registro-servicios` estuviera listo | `docker compose restart <servicio>` |
| `401` en rutas protegidas aunque mandas el token | `SECRET_KEY` distinto entre servicios | Confirma que todos usan el mismo `SECRET_KEY` (viene de la variable de entorno compartida en `docker-compose.yml` / `.env`) |
| `502 Bad Gateway` al crear producto/pedido | El Gateway no encuentra el servicio destino | Revisa `/gateway/servicios`; si falta la instancia, revisa logs de ese servicio |
| Puerto ya en uso al hacer `up` | Algo local ya usa 5432/6379/27017/8080 etc. | Libera el puerto o cambia el mapeo `"host:container"` en `docker-compose.yml` |
| `servicio-repartidores` no conecta a Mongo | El contenedor `mongo` tardó en iniciar | Espera unos segundos y `docker compose restart servicio-repartidores` |

## 9. Apagar todo

```powershell
docker compose down          # detiene y elimina los contenedores, conserva los volúmenes (datos)
docker compose down -v       # además borra los volúmenes (Postgres, Mongo, Redis, media) — empieza de cero
```

## 10. Kubernetes (cluster local, para la demo)

Los manifiestos de `k8s/` corren en cualquier cluster de Kubernetes. Para probarlo en tu propia PC sin nube ni costo, usa el Kubernetes integrado de Docker Desktop (ya lo tienes instalado).

`servicio-productos`, `servicio-negocios` y `servicio-usuarios` siguen usando Postgres externo (Supabase) y `servicio-repartidores` MongoDB Atlas — sus secrets siguen con placeholders `CAMBIAR-...`. `servicio-pedidos` usa SQL Server, pero ahora corre **dentro del propio cluster** (pod `sqlserver`, sin necesitar Azure ni cuenta externa), igual que en Docker Compose.

### 10.1 Habilitar el cluster (una sola vez)

Docker Desktop → ícono de engranaje (Settings) → **Kubernetes** → marca **Enable Kubernetes** → **Apply & Restart**. Espera a que el ícono de Kubernetes en Docker Desktop quede en verde.

Verifica:
```powershell
kubectl config use-context docker-desktop
kubectl get nodes
```
Debe mostrar un nodo `Ready`.

### 10.2 Construir las imágenes con el tag que esperan los manifiestos

El Kubernetes de Docker Desktop comparte el mismo Docker Engine que usas para `docker compose`, así que las imágenes que construyas quedan visibles para el cluster sin necesitar un registry. Solo hay que taggearlas como `llegaya/<servicio>:latest` (los `deployment.yaml` ya traen `imagePullPolicy: IfNotPresent`, para que Kubernetes use la imagen local en vez de intentar descargarla):

```powershell
docker build -t llegaya/registro-servicios:latest ./registro-servicios
docker build -t llegaya/config-server:latest ./config-server
docker build -t llegaya/api-gateway:latest ./api-gateway
docker build -t llegaya/servicio-usuarios:latest ./servicio-usuarios
docker build -t llegaya/servicio-negocios:latest ./servicio-negocios
docker build -t llegaya/servicio-productos:latest ./servicio-productos
docker build -t llegaya/servicio-pedidos:latest ./servicio-pedidos
docker build -t llegaya/servicio-repartidores:latest ./servicio-repartidores
```

### 10.3 Ajustar secrets antes de aplicar

Edita `k8s/secrets.yaml`:
- `SECRET_KEY`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`: pon valores de desarrollo (no necesitan ser reales para la demo, salvo que quieras probar el envío de correo).
- `sqlserver-secret.SA_PASSWORD`: déjalo en el valor por defecto o cámbialo por otra clave que cumpla la política de SQL Server (mayúscula + minúscula + número + símbolo, 8+ caracteres).
- `servicio-productos-db-secret` / `servicio-repartidores-db-secret`: solo hacen falta si vas a probar esos dos servicios contra sus bases reales; para la demo de la migración de `servicio-pedidos` no son necesarios.

### 10.4 Aplicar los manifiestos en orden

```powershell
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/redis/
kubectl apply -f k8s/sqlserver/
kubectl apply -f k8s/registro-servicios/
kubectl apply -f k8s/config-server/
kubectl apply -f k8s/api-gateway/
kubectl apply -f k8s/servicio-usuarios/ -f k8s/servicio-negocios/ -f k8s/servicio-productos/ -f k8s/servicio-pedidos/ -f k8s/servicio-repartidores/
```

`sqlserver` tarda ~20-30s en quedar listo; `servicio-pedidos` puede reiniciarse 1-2 veces mientras espera a que `sqlserver` acepte conexiones (comportamiento normal, Kubernetes lo reintenta solo).

### 10.5 Verificar

```powershell
kubectl get pods -n llegaya
kubectl get svc -n llegaya
```
Todos los pods deben quedar `Running` y `1/1 Ready` (dale 1-2 minutos a `servicio-pedidos` y `sqlserver`).

Para probar el API Gateway sin exponerlo con un LoadBalancer, usa port-forward:
```powershell
kubectl port-forward -n llegaya svc/api-gateway 8080:8080
```
Y en otra terminal, los mismos `Invoke-RestMethod` de la sección 5 apuntando a `http://localhost:8080`.

Para confirmar que `servicio-pedidos` de verdad usa SQL Server (y no una base en memoria), entra al pod de `sqlserver` y lista las tablas de `pedidos_db`, igual que se hizo en Docker Compose:
```powershell
kubectl exec -n llegaya deploy/sqlserver -- /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "CAMBIAR-Password123!" -C -d pedidos_db -Q "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES;"
```
(usa la misma password que hayas puesto en `sqlserver-secret`).

### 10.6 Apagar el cluster

```powershell
kubectl delete namespace llegaya
```
Esto borra todos los pods, services y PVCs del namespace (los datos de `sqlserver` y `servicio-usuarios`/`servicio-negocios` se pierden). Si solo quieres pausar sin perder datos, no borres el namespace: simplemente deja Docker Desktop corriendo, los pods siguen ahí la próxima vez que abras el equipo (o usa `kubectl scale deploy --all --replicas=0 -n llegaya` para apagar sin borrar).
