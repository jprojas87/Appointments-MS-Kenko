# appointments-service

Microservicio de citas de la sucursal virtual del proyecto Kenko. Permite consultar citas disponibles, agendar, reagendar y cancelar. Solo publica eventos (fase 4); no consume eventos de otros servicios ni llama a otros servicios.

## Estado de las fases

- [x] **Fase 1**: estructura, configuración, logging, errores, `/health`, Docker.
- [x] **Fase 2**: modelos, migraciones Alembic, repositorios y seeds.
- [ ] **Fase 3**: catálogo, API de citas, validación JWT, pruebas (incluida concurrencia).
- [ ] **Fase 4**: adaptador EventBridge (AWS real), `docs/events.md`.
- [ ] **Fase 5**: Terraform en `infra/terraform/`.

## Requisitos

- WSL2 (Ubuntu) con Docker y Docker Compose. El proyecto debe vivir en el sistema de archivos de WSL (`~/...`), no en `/mnt/c`.
- Nada más se requiere en el host: Python, PostgreSQL y las herramientas de prueba viven en los contenedores.

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

Para ejecutar uvicorn directamente en WSL (fuera de Docker), instala `requirements-dev.txt` en un venv, cambia `DATABASE_URL` a `@localhost:5433` y ejecuta `uvicorn app.main:create_app --factory --reload`.

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
- **Citas pasadas**: no hay estados ni procesos automáticos. Una cita es pasada si su fin (`date` + `end_time` en `America/Bogota`) ya ocurrió; se calcula en las consultas. Ningún proceso la marca como completada o fallida.
- **Errores**: formato uniforme `{"error": {"code", "message", "correlationId", "details"?}}`.
- **Correlation ID**: se toma del header `X-Correlation-Id` si es un UUID válido; si no, se genera (UUID v7). Se devuelve en la respuesta y aparece en todos los logs.
- **Logs**: JSON en stdout con `correlationId`, `eventId` y `userId` cuando aplique, sin datos sensibles innecesarios.
- **Health**: `GET /api/v1/health` no requiere autenticación. Responde `503` si la base de datos no responde.
- **Imagen de producción**: `runtime` (usuario no root, sin dependencias de desarrollo). La imagen `test` es solo para pruebas.

## TODO

- **JWT** (pendiente con el equipo de Authentication): confirmar el algoritmo, el emisor (`iss`), la audiencia (`aud`) y si el `sub` es el UUID del usuario. Hasta entonces solo se usa el claim `sub` como `userId`; no se inventan más claims.
- **Eventos**: nombres de colas y reglas, y contrato definitivo con Notifications y Profile, según lo acordado con el equipo.
- **Paginación y formato de `/appointments/me`** (`include_past`): se implementan en la fase 3.
