# Architecture

The app runs as four Docker containers on one private network. Nginx is the
only entry point for the web app; Django, gunicorn and PostGIS are not
reachable from the host.

## Components and network

```mermaid
flowchart LR
    subgraph host["Host machine"]
        browser["Browser<br/>Bootstrap 5 + Leaflet<br/>map.js"]
    end

    subgraph internet["Internet"]
        osm["OpenStreetMap<br/>tile servers"]
        cdn["jsDelivr / unpkg<br/>Bootstrap, Leaflet,<br/>markercluster (SRI pinned)"]
    end

    subgraph lbs["Docker network lbs · 172.28.0.0/16"]
        nginx["nginx<br/>nginx:1.27-alpine<br/>port 80 (published)"]
        web["web<br/>gunicorn, 3 workers<br/>Django 5.2 + DRF<br/>port 8000 (internal)"]
        db[("db<br/>postgis/postgis:16-3.4<br/>port 5432 (internal)")]
        pgadmin["pgadmin<br/>dpage/pgadmin4:9<br/>port 5050 (published)"]
    end

    static[["volume: static"]]
    pgdata[["volume: pgdata"]]
    pgadmindata[["volume: pgadmin_data"]]

    browser -- "HTTP :80<br/>pages, /api/, /static/" --> nginx
    browser -- "map tiles" --> osm
    browser -- "CSS / JS" --> cdn
    nginx -- "proxy_pass<br/>X-Forwarded-*" --> web
    nginx -. "serves /static/ directly" .- static
    web -- "collectstatic" --> static
    web -- "SQL (psycopg 3)<br/>GeoDjango ORM" --> db
    db --- pgdata
    browser -- "HTTP :5050" --> pgadmin
    pgadmin -- "SQL" --> db
    pgadmin --- pgadmindata
```

| Container | Image | Host port | Role |
|---|---|---|---|
| `nginx` | `nginx:1.27-alpine` | 80 | Reverse proxy. Serves `/static/` from the shared volume (cached 7 days, gzip), proxies everything else to gunicorn, sets security headers, hides its version. |
| `web` | built from `Dockerfile` (python:3.12-slim + GDAL/GEOS/PROJ) | none (`expose 8000`) | Django app under gunicorn, running as the non-root user `app`. |
| `db` | `postgis/postgis:16-3.4` | none | PostgreSQL 16 with PostGIS 3.4. Healthcheck with `pg_isready`. |
| `pgadmin` | `dpage/pgadmin4:9` | 5050 | Database admin UI. The server "AI Data Center Map DB" is pre-registered by `pgadmin/servers.json`. |

Start order: `db` becomes healthy, then `web` and `pgadmin` start, then
`nginx`. Nginx has its own healthcheck that fetches the login page through
the whole chain.

Volumes keep data across restarts: `pgdata` (database), `pgadmin_data`
(pgAdmin settings), `static` (files written by `collectstatic`, read by
Nginx).

All settings come from `.env` (see `.env.example`): database credentials,
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, allowed hosts, CSRF origins, the pgAdmin
login and the two test-account passwords.

## Start-up of the `web` container

`entrypoint.sh` runs these steps, then starts gunicorn. Every step is
idempotent, so a restart never duplicates data.

```mermaid
flowchart TD
    a["Wait for PostGIS<br/>(up to 30 tries)"] --> b["migrate"]
    b --> c["collectstatic<br/>(hashed file names)"]
    c --> d["load_countries<br/>Natural Earth polygons,<br/>skipped if loaded"]
    d --> e["import_datacenters --if-empty<br/>96 sites from the CSV,<br/>skipped if any exist"]
    e --> f["seed_users<br/>admin + demo,<br/>skipped if they exist"]
    f --> g["exec gunicorn"]
```

Geocoding (`geocode_datacenters`) is not part of start-up. It ran once
during development against Nominatim, and its output
`data/datacenters_geocoded.csv` is committed, so start-up needs no network
access to a geocoder.

## Code layers (MVC)

```mermaid
flowchart TB
    subgraph browser["Browser"]
        html["map.html<br/>server-rendered form"]
        js["static/js/map.js<br/>fetch + Leaflet"]
    end

    subgraph django["Django · ai_datacenters app"]
        urls["urls.py<br/>routing"]
        views["views.py<br/>MapView, SignupView<br/>(pages)"]
        api["api.py<br/>DataCenterViewSet,<br/>country_at, country_stats,<br/>filter_options (REST)"]
        perms["permissions.py<br/>IsStaffOrReadOnly"]
        filters["filters.py<br/>DataCenterFilter, BBoxField"]
        ser["serializers.py<br/>GeoJSON features,<br/>query-parameter checks"]
        spatial["spatial.py<br/>nearest, within, buffer,<br/>containment, bbox,<br/>country stats, nearest links"]
        models["models.py<br/>Country, DataCenter"]
        admin["admin.py<br/>GISModelAdmin (CRUD)"]
    end

    db[("PostGIS")]

    html --> urls
    js -- "JSON / GeoJSON" --> urls
    urls --> views
    urls --> api
    api --> perms
    api --> filters
    api --> ser
    api --> spatial
    views --> models
    filters --> spatial
    spatial --> models
    admin --> models
    models --> db
```

| MVC role | Django files |
|---|---|
| Model | `models.py` (fields, validators, `save()`/`delete()` that keep the derived country and nearest-site line correct), `spatial.py` (the spatial queries) |
| View (presentation) | `templates/` (HTML), `serializers.py` (GeoJSON representation), `static/` (CSS, JS) |
| Controller | `views.py` (pages), `api.py` (REST endpoints), `urls.py` (routing), `filters.py` and `permissions.py` |

## Security

| Area | Measure |
|---|---|
| Exposure | Only Nginx (80) and pgAdmin (5050) are published. Django and PostGIS are reachable only on the `lbs` network. |
| Secrets | All in `.env`, which is git-ignored. `.env.example` holds placeholders only. pgAdmin's `servers.json` stores no password. |
| Django | `DEBUG=False` by default, explicit `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, `HttpOnly` + `SameSite=Lax` cookies, CSRF on every form and on API writes, password validators on sign-up. |
| API | Every endpoint needs a login. Both methods are enabled: the session cookie (browser) and `Authorization: Token` (API clients). Only staff can create, edit or delete. Query parameters are validated (400 with field errors). Text from the data is inserted with `textContent` in the browser, never as HTML. |
| Headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `server_tokens off`. |
| Containers | gunicorn runs as an unprivileged user; request bodies are capped at 2 MB. |
| Front-end assets | CDN files are pinned to exact versions with Subresource Integrity hashes. |
