# docker-compose.yml

**Path:** `docker-compose.yml`

## Services

| Service | Image / Build | Ports | Depends On |
|---------|---------------|-------|------------|
| `postgres` | `postgres:16-alpine` |  |  |
| `autoresearch` | build: `.` | `${AUTORESEARCH_BIND_HOST:-127.0.0.1}:${AUTORESEARCH_PORT:-8030}:8000` | `{'postgres': {'condition': 'service_healthy'}}` |

### postgres

- **Image:** `postgres:16-alpine`
- **Volumes:** `postgres-data:/var/lib/postgresql/data`
- **Environment:** `{'POSTGRES_USER': 'autoresearch', 'POSTGRES_PASSWORD': 'autoresearch', 'POSTGRES_DB': 'autoresearch'}`

### autoresearch

- **Build context:** `.`
- **Ports:** `${AUTORESEARCH_BIND_HOST:-127.0.0.1}:${AUTORESEARCH_PORT:-8030}:8000`
- **Volumes:** `workspace-data:/app/workspace`, `host-configs:/host/configs`
- **Environment:** `{'AUTORESEARCH_DATABASE_URL': '${AUTORESEARCH_DATABASE_URL-postgresql://autoresearch:autoresearch@postgres:5432/autoresearch}'}`
- **Depends on:** `{'postgres': {'condition': 'service_healthy'}}`

## Named Volumes

- `postgres-data`
- `workspace-data`
- `host-configs`

## Notes

_Add reviewed operational context here; generated sections are replaced from source observations._
