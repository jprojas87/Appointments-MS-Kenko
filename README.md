# appointments-service

Microservicio de citas de la sucursal virtual del proyecto Kenko. Permite consultar citas disponibles, agendar, reagendar y cancelar. Solo publica eventos (fase 4); no consume eventos de otros servicios ni llama a otros servicios.

## Estado de las fases

- [x] **Fase 1**: estructura, configuración, logging, errores, `/health`, Docker.
- [x] **Fase 2**: modelos, migraciones Alembic, repositorios y seeds.
- [x] **Fase 3**: catálogo, API de citas, validación JWT, pruebas (incluida concurrencia). Eventos con `FakePublisher` (fase 4 lo sustituye por EventBridge).
- [ ] **Fase 4**: adaptador EventBridge (AWS real), `docs/events.md`.
- [ ] **Fase 5**: Terraform en `infra/terraform/`.

## Requisitos

- WSL2 (Ubuntu) con Docker y Docker Compose. El proyecto debe vivir en el sistema de archivos de WSL (`~/...`), no en `/mnt/c`.
- Nada más se requiere en el host: Python, `uv`, PostgreSQL y las herramientas de prueba viven en los contenedores.

## Puesta en marcha

```bash
cp .env.example .env          # ajusta los valores si hace falta
docker compose up --build     # levanta appointments-db y appointments-api
```

Primera vez, aplica migraciones y carga datos de prueba (ver [Base de datos](#base-de-datos)):

```bash
docker compose run --rm appointments-api alembic upgrade head
docker compose run --rm appointments-api python -m seeds.run
```

Verificación (ajusta el puerto si cambiaste `API_HOST_PORT`):

```bash
curl -s http://localhost:8000/api/v1/health
# {"status":"ok","checks":{"process":"ok","database":"ok"}}
```

Documentación interactiva (solo en desarrollo): `http://localhost:8000/api/v1/docs`.

## API

Prefijo `/api/v1`. Todo requiere `Authorization: Bearer <JWT>` excepto `/health`. El paciente se identifica **solo** por el claim `sub` del token; nunca se acepta un `userId` en el body ni en los parámetros.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Proceso y base de datos. Sin autenticación. |
| GET | `/catalog/medical-centers` | Centros médicos. |
| GET | `/catalog/physicians?specialty=&medical_center_id=` | Médicos, filtrables por tipo o sede (principal o secundaria). |
| GET | `/catalog/appointment-types` | `GENERAL`, `ODONTOLOGIA`, `PSICOLOGIA`. |
| GET | `/appointments/available?type=&medical_center_id=&physician_id=&date_from=&date_to=&page=&page_size=` | Citas libres, futuras y dentro de la ventana de agendamiento. |
| GET | `/appointments/me?include_past=false&page=&page_size=` | Mis citas. Por defecto solo futuras. |
| POST | `/appointments/{id}/schedule` | Agenda una cita libre. |
| POST | `/appointments/{id}/cancel` | Cancela una cita propia. |
| POST | `/appointments/{id}/reschedule` | Body `{"newAppointmentId": "..."}`. Cambia atómicamente la cita propia por otra libre. |

Parámetros de consulta en `snake_case`; JSON de entrada y salida en `camelCase`. Horas en formato `HH:MM`.

**Paginación:** `page` (≥1, por defecto 1) y `page_size` (1 a 100, por defecto 20). Respuesta: `{"items", "page", "pageSize", "total"}`. Orden: fecha, hora, `appointmentId`.

**Respuesta de reagendar:** `{"previousAppointment": {...}, "appointment": {...}}`.

**Errores:** `401` token ausente o inválido; `403` cita de otro usuario; `404` cita inexistente; `409` cita ya tomada; `422` regla de negocio o validación (`code` = `business_rule_violation` o `validation_error`).

**Reglas** (configurables por entorno):
- Agendar: la cita debe ser futura (inicio posterior a ahora) y dentro de `MAX_DAYS_AHEAD_TO_SCHEDULE` días.
- Cancelar y reagendar la cita actual: al menos `MIN_HOURS_BEFORE_CANCEL_OR_RESCHEDULE` horas antes del inicio.
- Reagendar: la nueva cita debe ser del mismo tipo, estar libre, ser futura y cumplir la ventana de agendamiento. Si la nueva ya no está libre, responde `409` y la cita actual no cambia.
- Las horas se evalúan en `America/Bogota`.

**Concurrencia:** agendar usa `UPDATE ... WHERE user_id IS NULL`; reagendar bloquea ambas filas en orden de `appointment_id`. Un solo ganador por cita; los demás reciben `409`.

**Eventos:** `AppointmentScheduled`, `AppointmentRescheduled` y `AppointmentCancelled` se publican solo después del commit, con reintentos acotados (3 intentos, backoff 0.2 s y 0.4 s). Si todos fallan se registra el error y la operación se mantiene. Esto se sustituye por Transactional Outbox si el volumen o la criticidad lo requieren (ver `docs/events.md` en la fase 4).

**Probar la API con un token de desarrollo** (usa `JWT_SECRET` de tu `.env`):

```bash
TOKEN=$(docker compose run --rm appointments-api python -c \
  "import jwt,os,time,uuid; print(jwt.encode({'sub': str(uuid.uuid4()), 'exp': int(time.time())+3600}, os.environ['JWT_SECRET'], algorithm='HS256'))")
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8080/api/v1/appointments/available?page_size=2"
```

## Base de datos

Esquema en `migrations/versions/` (Alembic). Tablas: `appointments`, `physicians`, `medical_centers` y el tipo `appointment_type` (`GENERAL`, `ODONTOLOGIA`, `PSICOLOGIA`).

```bash
docker compose run --rm appointments-api alembic upgrade head      # aplicar migraciones
docker compose run --rm appointments-api alembic downgrade -1      # revertir la última
docker compose run --rm appointments-api alembic current           # revisión actual
```

Una cita con `user_id` nulo está disponible; con `user_id`, está agendada por ese usuario. `user_id` no tiene clave foránea porque el id llega en el JWT y no hay tabla de usuarios aquí.

**Seeds** (`python -m seeds.run`): son idempotentes. Crean 5 centros médicos, 10 médicos (4 GENERAL, 3 ODONTOLOGIA, 3 PSICOLOGIA; algunos con sede secundaria) y citas de 30 minutos de lunes a viernes, en bloques 08:00–12:00 y 14:00–17:00, para los 60 días siguientes a hoy (zona America/Bogota). Cada médico atiende un día por semana, así que no hay solapamientos. Los IDs son UUID v5 deterministas. Una segunda ejecución no inserta nada ni modifica citas reservadas.

Pruebas de integración usan una base aparte `appointments_test` que el propio test crea y migra; no tocan los datos de desarrollo.

Para detener: `docker compose down` (la BD conserva sus datos en el volumen `appointments-db-data`; usa `docker compose down -v` para borrarlos).

## Pruebas y lint

Todo se ejecuta dentro de Docker:

```bash
docker compose --profile tools run --rm appointments-tests          # pytest
docker compose --profile tools run --rm appointments-tests ruff check .
docker compose --profile tools run --rm appointments-tests ruff format --check .
```

Las pruebas de integración requieren `appointments-db` sano; el servicio de pruebas lo espera automáticamente.

## Dependencias y uv

`pyproject.toml` es la fuente de verdad de las dependencias y `uv.lock` fija las versiones directas y transitivas. La versión de uv se fija en `0.13.0` en el Dockerfile; solo se usa durante build y para mantener el lock, no se incluye en la imagen runtime. No se requiere instalar uv ni Python en WSL.

Las imágenes de producción y de pruebas instalan dependencias con el lock en modo estricto (`uv sync --locked`). Para actualizar/verificar el lockfile, el contenedor `appointments-uv` del perfil `tools` monta el repo. Ejecútalo como tu UID para que los archivos del host conserven el propietario correcto:

```bash
docker compose --profile tools run --rm --user "$(id -u):$(id -g)" appointments-uv lock
docker compose --profile tools run --rm --user "$(id -u):$(id -g)" appointments-uv lock --check
```

Después de cambiar dependencias, reconstruye y valida las imágenes:

```bash
docker compose --profile tools build appointments-api appointments-tests
docker compose --profile tools run --rm appointments-tests pytest
docker compose --profile tools run --rm appointments-tests ruff check .
docker compose --profile tools run --rm appointments-tests ruff format --check .
```

## Variables de entorno

Todo se configura por entorno (`app/config.py`). La plantilla está en `.env.example` con comentarios.

| Variable | Descripción |
|---|---|
| `ENVIRONMENT` | `local`, `dev` o `prod`. |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` o `ERROR`. |
| `DATABASE_URL` | Cadena SQLAlchemy con driver `psycopg`. |
| `POSTGRES_*`, `POSTGRES_HOST_PORT`, `API_HOST_PORT` | Solo para docker-compose. |
| `AWS_REGION` | Región de AWS (`us-east-1`). Se usará en la fase 4. |
| `EVENT_BUS_NAME` | Bus de EventBridge (`kenko-dev-bus` / `kenko-prod-bus`). |
| `JWT_ALGORITHM` | `HS256` (desarrollo) o `RS256`. |
| `JWT_SECRET` | Secreto para HS256. Obligatorio con HS256. |
| `JWT_PUBLIC_KEY` | Clave pública PEM para RS256. Obligatoria con RS256. |
| `JWT_ISSUER`, `JWT_AUDIENCE` | Opcionales. Ver TODO de JWT. |
| `MIN_HOURS_BEFORE_CANCEL_OR_RESCHEDULE` | Anticipación mínima para cancelar o reagendar. Por defecto `24`. |
| `MAX_DAYS_AHEAD_TO_SCHEDULE` | Días máximos de antelación para agendar. Por defecto `90`. |

Las credenciales de AWS nunca van en el repositorio ni en `.env`: en AWS real se usa un rol IAM; en desarrollo, el perfil o las variables de entorno estándar de AWS.

## Decisiones

- **Zona horaria**: fechas y horas de las citas (`date`, `start_time`, `end_time`) se interpretan en `America/Bogota`. Los timestamps de eventos (`occurredAt`, `scheduledAt`, etc.) van en UTC con sufijo `Z`.
- **Citas pasadas**: no hay estados ni procesos automáticos. Una cita es futura si su inicio (`date` + `start_time` en `America/Bogota`) aún no ha llegado; se calcula en las consultas. Ningún proceso la marca como completada o fallida.
- **Errores**: formato uniforme `{"error": {"code", "message", "correlationId", "details"?}}`.
- **Cancelar cita de otro usuario**: `403` (no `404`), para que el mensaje sea claro al usuario autenticado. Los IDs son UUID v4/v7, así que no son adivinables.
- **Correlation ID**: se toma del header `X-Correlation-Id` si es un UUID válido; si no, se genera (UUID v7). Se devuelve en la respuesta y aparece en todos los logs.
- **Logs**: JSON en stdout con `correlationId`, `eventId` y `userId` cuando aplique, sin datos sensibles innecesarios.
- **Health**: `GET /api/v1/health` no requiere autenticación. Responde `503` si la base de datos no responde.
- **Imagen de producción**: `runtime` (usuario no root, sin dependencias de desarrollo). La imagen `test` es solo para pruebas.

## TODO

- **JWT** (pendiente con el equipo de Authentication): confirmar si `iss` y `aud` son obligatorios. Hoy solo se validan si se configuran `JWT_ISSUER` o `JWT_AUDIENCE`. Se exige `sub` (UUID) y se valida `exp` si viene. No se inventan más claims.
- **Pruebas de servicios**: las pruebas de agendar, cancelar y reagendar son de integración contra PostgreSQL real, porque la atomicidad (locks y UPDATE condicional) no se puede validar con mocks ni con SQLite.
- **Eventos**: nombres de colas y reglas, y contrato definitivo con Notifications y Profile, según lo acordado con el equipo.
- **Paginación y formato de `/appointments/me`** (`include_past`): se implementan en la fase 3.
