# AI Data Center Map

A location-based services web app that shows the map with the world's largest AI data
centers. Signed-in users explore 96 sites from the
[Epoch AI data centers dataset](https://epoch.ai/data/data-centers-documentation) on an
interactive Leaflet map, filter them by owner, country, power, cost and
computing power, and run spatial searches: the nearest sites to a point,
every site within a radius, and the country under a point. Staff users
create, edit and delete sites in the Django admin or through the REST API.

![Map page on a desktop: the United States with clustered sites, filtered by country](docs/screenshots/map-desktop.png)

## Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Technology stack](#technology-stack)
- [Setup (local Docker deployment)](#setup-local-docker-deployment)
- [Test credentials](#test-credentials)
- [User guide](#user-guide)
- [API documentation](#api-documentation)
- [Tests](#tests)
- [Project structure](#project-structure)
- [Known issues and limitations](#known-issues-and-limitations)
- [References](#references)
- Separate documents: [architecture](docs/architecture.md),
  [database schema](docs/schema.md),
  [spatial SQL for pgAdmin](docs/sql/spatial_queries.sql)

## Features

**Map**
- OpenStreetMap tiles (greyscale), zoom and pan with mouse, touch or keyboard.
- One circle per site, its area proportional to the chosen measure: IT power
  (MW), capital cost ($B) or H100 equivalents. A legend shows reference sizes.
- Nearby sites group into numbered clusters that split apart as you zoom in.
- Popups with owner, users, country, power, cost, H100e and the distance to
  the nearest other site. Hovering or focusing a circle shows its value.
- Layers: a choropleth of total MW per country (with a "Show as table"
  version), and "Cluster links": a line from each site to its nearest
  neighbour.

**Search and filters**
- Free-text search over site, owner, users, address and country, as you type.
- Filters: owners (several at once), country, and min/max ranges for MW,
  cost and H100e. Active filters show as removable chips.
- "Only sites in map view" limits the list to the visible map area and
  updates as you pan.
- Sites list: every matching site; selecting one zooms to it and opens its
  popup.

**Spatial searches** (Nearby tab, or tap the map on a phone)
- Nearest 5 sites to a point, with a dashed line to each.
- All sites within a radius (1–5000 km), with the search circle drawn.
- Country here: the country under the point, outlined, with its totals and
  sites.
- All three use the current search and filters, so "Nearest 5" with the
  search "Meta" finds the 5 nearest Meta sites. Changing the search or
  filters updates the results.

**Accounts and data management**
- Sign up, log in, log out. The map and the API need a login.
- Staff: full create, read, update and delete in the Django admin (with a map
  widget to place the point) or through the REST API. The country and the
  nearest-site line update automatically after every change.
- REST API with GeoJSON responses, both session and token authentication
  (the browser uses its session, scripts and API clients use a token), and
  Swagger docs.

**Design**
- Responsive from 280 px phones to wide desktops, portrait and landscape.
- Accessible, targeting WCAG 2.1 AA: full keyboard use (site circles and
  clusters are buttons), visible focus, labelled controls, errors in text,
  live result counts, 44 px touch targets, reduced-motion support, no
  colour-only information. axe-core reports no violations.

## Screenshots

### Map, search and filters

| | |
|---|---|
| ![Popup of Colossus 2 with owner, users, country, power, cost, H100e and nearest site](docs/screenshots/popup.png) | ![Four active filters shown as removable chips, 25 results](docs/screenshots/filters.png) |
| A site popup (Colossus 2), opened from the Sites list | Filters as removable chips: owners Google and Meta, IT power ≥ 100 MW, capital cost ≥ $1B, H100e ≥ 50k |
| ![Only sites in map view: 45 results in the north-east United States](docs/screenshots/in-map-view.png) | ![Panel explaining IT power, capital cost and H100 equivalents](docs/screenshots/measures-help.png) |
| "Only sites in map view": the list shows the 45 sites in view and updates on pan | The ⓘ panel explaining the three measures |

### Spatial searches

| | |
|---|---|
| ![Nearest five sites to a point near Omaha, with dashed lines](docs/screenshots/nearest.png) | ![33 sites within 1,000 km of a point in Oklahoma, with the search circle](docs/screenshots/within-radius.png) |
| Nearest 5 sites near Omaha, with a dashed line to each | Find within 1,000 km: the search circle and 33 sites, closest first |
| ![Country here: the United States outlined, with its totals and sites](docs/screenshots/country-here.png) | ![Cluster links joining each site to its nearest neighbour, circles sized by H100e](docs/screenshots/cluster-links.png) |
| Country here: the United States outlined, with its totals (77 sites, 12,374 MW, $468.8B) | Cluster links: each site joined to its nearest other site; circles sized by H100 equivalents |

### Choropleth

| | |
|---|---|
| ![Choropleth of total MW per country with a hover tooltip](docs/screenshots/choropleth.png) | ![Choropleth legend with the Show as table list of countries](docs/screenshots/choropleth-table.png) |
| Choropleth of MW per country, with its legend and a country tooltip | "Show as table": the same figures as text (the accessible version) |

### Validation and errors

| | |
|---|---|
| ![Filter menu with the error: the minimum is larger than the maximum](docs/screenshots/filter-error.png) | ![Radius field with the error: enter a radius from 1 to 5000 km](docs/screenshots/radius-error.png) |
| Filter validation: the minimum is larger than the maximum (focus moves to the field) | Radius validation: from 1 to 5000 km |
| ![No sites match this search and these filters, with a Reset button](docs/screenshots/empty-state.png) | ![Sign-up form with errors: username taken, passwords do not match](docs/screenshots/signup-errors.png) |
| Empty state with a Reset button | Sign-up errors under each field |

### Tablet and phone

| | |
|---|---|
| ![Map on a tablet in portrait](docs/screenshots/tablet-map.png) | ![Tablet with the Sites list panel open from the side](docs/screenshots/tablet-panel.png) |
| Tablet (768 px, portrait) | Tablet: the ☰ panel with the Sites list |

<p>
  <img src="docs/screenshots/phone-map.png" alt="Map on a phone, zoomed to the United States with clustered sites" width="240">
  <img src="docs/screenshots/phone-point.png" alt="Nearby search popup after tapping the map on a phone" width="240">
  <img src="docs/screenshots/phone-results.png" alt="Nearest five sites listed in the bottom sheet on a phone" width="240">
</p>

Phone: the map, the popup after tapping the map, and the nearest sites in the bottom sheet.

### Data management and API

| | |
|---|---|
| ![Django admin form for Colossus 2 with the map widget to move the point](docs/screenshots/admin-edit.png) | ![Django admin list of data centers](docs/screenshots/admin-list.png) |
| Staff edit a site in the Django admin; the map widget moves its point | Django admin list with filters by owner, country and precision |
| ![Swagger UI listing every API endpoint](docs/screenshots/swagger.png) | ![Swagger UI for the nearest endpoint, showing its query parameters](docs/screenshots/swagger-nearest.png) |
| Swagger UI: every endpoint (<http://localhost/api/docs/>) | The nearest endpoint with its parameters (lat and lon required, plus the list filters) |

### Database (pgAdmin)

| | |
|---|---|
| ![pgAdmin Query Tool running the radius search SQL with 35 result rows](docs/screenshots/pgadmin-query.png) | ![pgAdmin Geometry Viewer showing the buffer circle, the sites and lines to them](docs/screenshots/pgadmin-geometry.png) |
| A spatial query in the pgAdmin Query Tool | Its result in the Geometry Viewer: a polygon (buffer), points (sites) and lines |

![pgAdmin listing the three GiST spatial indexes](docs/screenshots/pgadmin-indexes.png)

The GiST spatial indexes on `location`, `nearest_link` and `geom`.

### Accounts

| | |
|---|---|
| ![Sign-in page](docs/screenshots/login.png) | ![Create account page](docs/screenshots/signup.png) |
| Sign in | Create an account |

## Technology stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 16 + PostGIS 3.4 (`postgis/postgis:16-3.4`), managed with pgAdmin 4 (`dpage/pgadmin4:9`) |
| Back end | Python 3.12, Django 5.2 with GeoDjango, Django REST Framework, djangorestframework-gis, django-filter, drf-spectacular, gunicorn |
| Front end | Bootstrap 5.3.8, Leaflet 1.9.4, Leaflet.markercluster 1.5.3, plain JavaScript (no build step) |
| Map data | OpenStreetMap tiles, Natural Earth 1:50m country borders |
| Deployment | Docker Compose: `web` (Django + gunicorn), `db` (PostGIS), `pgadmin`, `nginx` (reverse proxy) on the custom network `lbs` (172.28.0.0/16) |
| Testing | pytest, pytest-django, pytest-cov; Playwright + axe-core for browser and accessibility checks |

See [docs/architecture.md](docs/architecture.md) for the component diagram.

## Setup (local Docker deployment)

**Requirements:** Docker Desktop (or Docker Engine with the Compose v2
plugin), git, free ports **80** and **5050**, and an internet connection
(map tiles and the CDN-hosted CSS/JS load in the browser).

### 1. Get the code

```bash
git clone <this repository>
cd advanced-web-mapping-ca1
```

### 2. Configure the environment

```bash
cp .env.example .env
```

Open `.env` and replace every `change-me` value:

| Variable | Purpose |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Database. Keep `POSTGRES_DB` and `POSTGRES_USER` as `ai_datacenters`, the names `pgadmin/servers.json` uses |
| `DJANGO_SECRET_KEY` | A long random string, e.g. from `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `False` (default). `True` only for local debugging |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated host names and origins |
| `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD` | pgAdmin login |
| `SEED_ADMIN_PASSWORD`, `SEED_DEMO_PASSWORD` | Passwords of the two test accounts |

### 3. Build the image

```bash
docker compose build
```

This builds the `web` image from the `Dockerfile`: Python 3.12 with GDAL,
GEOS and PROJ, the packages in `requirements.txt`, and the project code.
The other three services use ready-made images (`postgis/postgis`,
`dpage/pgadmin4`, `nginx`), which Compose downloads on the first start.

### 4. Start the containers

```bash
docker compose up -d
```

`-d` runs them in the background. Steps 3 and 4 can be combined as
`docker compose up -d --build`. Follow the start-up with:

```bash
docker compose logs -f web
```

The first start takes longer: `entrypoint.sh` waits for PostGIS, runs the
migrations, collects the static files, loads 242 country borders, imports
the 96 data centers and creates the test accounts. It is ready when the log
shows `Listening at: http://0.0.0.0:8000`. Press Ctrl+C to stop following
the log (the containers keep running). Later starts skip the data loads.

Check that every service is up:

```bash
docker compose ps
```

`db` and `nginx` show `(healthy)`; `web` and `pgadmin` show `Up`.

### 5. Open the app

| Service | URL | Notes |
|---|---|---|
| App | <http://localhost> | Sign in with a [test account](#test-credentials) |
| API docs (Swagger) | <http://localhost/api/docs/> | Needs a login |
| Django admin | <http://localhost/admin/> | Staff only (`admin`) |
| pgAdmin | <http://localhost:5050> | Log in with `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD`. The server "AI Data Center Map DB" is already listed; enter `POSTGRES_PASSWORD` once |

Only Nginx (80) and pgAdmin (5050) are published on the host. Django
(port 8000) and PostGIS (5432) are reachable only inside the Docker network.

### 6. Run the tests

```bash
docker compose exec web pytest
```

See [Tests](#tests) for coverage and what each file covers.

## Test credentials

Two accounts are created on the first start by the `seed_users` command:

| Username | Password | Role |
|---|---|---|
| `admin` | value of `SEED_ADMIN_PASSWORD` in `.env` | Staff and superuser: map, Django admin, API writes |
| `demo` | value of `SEED_DEMO_PASSWORD` in `.env` | Regular user: map and read-only API |

Passwords are not stored in the repository. If `.env` is copied from
`.env.example` without changes, both passwords are `change-me`. Anyone can
also create a regular account at `/accounts/signup/`.

## User guide

1. **Sign in** at <http://localhost> with `demo` (or [sign up](http://localhost/accounts/signup/)). The map shows
   every site; the count above the map says how many match.
2. **Explore the map.** Drag or use the arrow keys to pan, scroll, pinch or
   `+`/`−` to zoom. Click a numbered cluster to zoom into it. Click a circle
   for its details; hover it to see its value.
3. **Change what the circles show.** The toggles next to Filter size the
   circles by IT Power (MW), Capital cost ($B) or H100 equivalents. The ⓘ
   button explains each measure.
4. **Search.** Type in the search box (shortcut **Ctrl+K**, or **⌘K** on a
   Mac), for example `texas`, `Meta` or `Stargate`. The map and list update
   as you type.
5. **Filter.** Open **Filter** to choose owners (Ctrl/⌘ for several), a
   country, and min/max values, then press **Apply**. Each active filter
   appears as a chip under the toolbar; click its × to remove it. Tick
   **Only sites in map view** to list just the sites you can see.
6. **Sites list.** The *Sites list* tab (the ☰ button on phones and tablets)
   lists every matching site. Select one to zoom to it and open its popup.
7. **Search near a point.** On a desktop, click the map (an ✕ marks the
   point) or press **Use map centre** in the *Nearby* tab, then choose:
   - **Nearest 5 sites**: dashed lines to the five closest sites.
   - **Find within … km**: set the radius (1–5000 km) first; the circle and
     the sites inside it appear.
   - **Country here**: outlines the country and lists its totals and sites.

   On a phone, tap the map and pick a search in the popup. Results are
   numbered and sorted by distance; select one to show it. **Clear point and
   results** removes the search.

   These searches only look at sites that match the search box and the
   filters (but not "Only sites in map view"), and the note "Only sites
   that match your search and filters" says so. Change the search or a
   filter and the results update.
8. **Layers** (top right of the map, a button on phones): **Choropleth**
   shades countries by total MW (use **Show as table** for the figures);
   **Cluster links** joins each site to its nearest neighbour.
9. **Keyboard.** Every control works with Tab, Enter and Space. Site
   circles and clusters are in the Tab order. **Escape** closes popups,
   menus and tooltips.
10. **Manage data (staff).** Sign in as `admin` and open **Admin** in the top
    bar. Under *Data centers* you can add, edit or delete sites; move a
    site by placing its point on the map widget. The country and the nearest-site
    lines update on save.

## API documentation

**Interactive docs (Swagger UI): <http://localhost/api/docs/>**. Sign in at
<http://localhost> first; the docs need a login like the rest of the API. The
OpenAPI 3 schema is at <http://localhost/api/schema/>.

Base URL `http://localhost/api/`. Every endpoint needs authentication: the
browser session (after signing in), or a token in the header
`Authorization: Token <key>`. Responses are JSON; site lists are GeoJSON
`FeatureCollection`s with `Point` geometries.

| Method and path | Description | Who |
|---|---|---|
| `POST /api/token/` | Body `username`, `password`; returns `{"token": "..."}` | anyone |
| `GET /api/datacenters/` | All sites, filtered by the parameters below | logged in |
| `POST /api/datacenters/` | Create a site (GeoJSON Feature) | staff |
| `GET /api/datacenters/{id}/` | One site | logged in |
| `PUT` / `PATCH /api/datacenters/{id}/` | Update a site | staff |
| `DELETE /api/datacenters/{id}/` | Delete a site | staff |
| `GET /api/datacenters/nearest/?lat=&lon=&n=` | The `n` nearest sites (default 5, max 20), closest first, each with `distance_km` and a `link` LineString from the point. Accepts the list filters | logged in |
| `GET /api/datacenters/within/?lat=&lon=&km=` | Sites within `km` (0 < km ≤ 5000): `{"buffer": Polygon, "sites": FeatureCollection}`. Accepts the list filters | logged in |
| `GET /api/countries/at/?lat=&lon=` | The country containing the point with its totals, and its sites: `{"country": Feature, "sites": FeatureCollection}`; 404 in the sea. Accepts the list filters; the totals count only matching sites | logged in |
| `GET /api/countries/stats/` | Countries with at least one site: polygon, `site_count`, `total_mw`, `total_cost_busd` | logged in |
| `GET /api/filters/` | Owners, countries and the min/max of MW, cost and H100e | logged in |

**List filters** (`GET /api/datacenters/`, all bounds inclusive, all
combinable; `nearest`, `within` and `countries/at` accept them too, e.g.
`/api/datacenters/nearest/?lat=32.78&lon=-96.80&owner=Meta`):

| Parameter | Example | Meaning |
|---|---|---|
| `owner` | `?owner=Google&owner=Meta` | One or more owners (unknown owner: 400) |
| `country` | `?country=Malaysia` | Country name |
| `mw_min`, `mw_max` | `?mw_min=100` | IT power range, MW |
| `cost_min`, `cost_max` | `?cost_max=10` | Capital cost range, billions of 2025 USD |
| `h100e_min`, `h100e_max` | `?h100e_min=100000` | H100-equivalent range |
| `search` | `?search=texas` | Text in name, owner, users, address or country |
| `bbox` | `?bbox=-90,30,-70,45` | Only sites in the box `min_lon,min_lat,max_lon,max_lat` |

**Site fields:** `id`, `name`, `owner`, `users`, `country` (read-only, from
the location), `power_mw`, `capital_cost_busd`, `h100e`, `address`,
`geocode_precision` (`address`, `postcode`, `city`, `manual`),
`nearest_link` and `nearest_km` (read-only).

**Errors:** `400` with a message per field (for example
`{"lat": ["Ensure this value is less than or equal to 90."]}`), `401`/`403`
without a login or for a non-staff write, `404` for an unknown id or a point
outside every country.

**Examples**

```bash
# Get a token
TOKEN=$(curl -s -X POST http://localhost/api/token/ \
  -d username=demo -d password="$SEED_DEMO_PASSWORD" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Google and Meta sites of 100 MW or more
curl -H "Authorization: Token $TOKEN" \
  "http://localhost/api/datacenters/?owner=Google&owner=Meta&mw_min=100"

# 5 nearest sites to Dallas, and every site within 500 km
curl -H "Authorization: Token $TOKEN" "http://localhost/api/datacenters/nearest/?lat=32.78&lon=-96.80"
curl -H "Authorization: Token $TOKEN" "http://localhost/api/datacenters/within/?lat=32.78&lon=-96.80&km=500"

# Create a site (staff token)
curl -X POST -H "Authorization: Token $ADMIN_TOKEN" -H "Content-Type: application/json" \
  http://localhost/api/datacenters/ -d '{
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [-6.26, 53.35]},
    "properties": {"name": "Example Dublin", "owner": "Example", "power_mw": 50,
                   "capital_cost_busd": 1.5, "h100e": 20000, "geocode_precision": "manual"}
  }'
```

## Tests

```bash
docker compose exec web pytest                       # run all tests
docker compose exec web pytest --cov=ai_datacenters  # with a coverage report
```

The tests run inside the `web` container against a real PostGIS test
database, because the spatial queries need PostGIS. They use small
hand-made geometries (a square "Testland" country and points at known
distances), so the expected results are exact. Nominatim is mocked; no test
uses the network. Line coverage of the app code is 91% (`.coveragerc` leaves out
the tests and migrations); the gap is the development-only geocoding command, which
calls Nominatim.

| Test file | Covers |
|---|---|
| `test_setup.py` | PostGIS is available |
| `test_models.py` | Validation, unique names, country set from the point |
| `test_geocoding.py`, `test_import.py`, `test_load_countries.py`, `test_seed_users.py` | Geocoding fallback chain, idempotent data loading, test accounts |
| `test_nearest_links.py` | Stored nearest-site lines after save, move, delete and admin bulk delete |
| `test_api_list.py` | GeoJSON list, every filter, bounding box, search, 400 on bad values |
| `test_api_spatial.py` | Nearest, radius + buffer, containment, country stats, parameter validation |
| `test_permissions.py` | Anonymous, regular and staff access; token auth; invalid writes |
| `test_views.py` | Login, sign-up, logout, redirects, map page content |

The project was built test-first: for each feature a failing test came
first (`test:` commits in the history), then the code that makes it pass
(`feat:`/`fix:`). The JavaScript is checked in a real browser with
Playwright (each page at 280–1440 px, keyboard-only use, axe-core
accessibility scans) rather than with unit tests.

## Project structure

```
ai_datacenter_map/       Django project: settings (from environment), root URLs, WSGI
ai_datacenters/          The app
  models.py              Country (MultiPolygon), DataCenter (Point + LineString)
  spatial.py             All spatial queries (GeoDjango ORM)
  api.py                 REST endpoints (DRF)
  views.py               HTML pages: map, sign-up
  serializers.py         GeoJSON serializers, query-parameter validation
  forms.py               Login and sign-up forms (Bootstrap styling)
  filters.py             List filters, bounding-box parsing
  permissions.py         IsStaffOrReadOnly
  admin.py               GIS admin (staff CRUD)
  geocoding.py           Nominatim fallback chain (development only)
  management/commands/   geocode_datacenters, import_datacenters, load_countries, seed_users
  migrations/            Database schema
  tests/                 pytest suite
templates/               base and map pages
  registration/          Login and sign-up pages
  includes/field.html    One form field with its label and errors
static/                  css/app.css, js/map.js, img/favicon.svg
data/                    Geocoded sites CSV, manual coordinate overrides, Natural Earth borders
docs/                    Architecture, schema, spatial SQL, screenshots
nginx/default.conf       Reverse proxy
pgadmin/servers.json     Pre-registered pgAdmin server
Dockerfile, docker-compose.yml, entrypoint.sh, requirements.txt, .env.example, pytest.ini, .coveragerc
```

## Known issues and limitations

- **Geocoding precision.** Epoch AI gives addresses, not coordinates. Of
  the 96 sites, 51 were placed at address level, 1 at postcode level, 27 at
  city level and 17 by hand (sites with only a country or a wrong geocoder
  match, placed from public reports). City-level points can be several
  kilometres from the real site. The precision of each site is stored in
  `geocode_precision`.
- **Shared coordinates.** Sites with the same address (for example the
  campuses at Abilene, Richmond and Lake Mariner) sit on the same point, so
  their nearest-site distance is 0 km and their circles overlap.
- **US-heavy data.** 77 of the 96 sites are in the United States, so the
  choropleth is mostly one dark country.

## References

**Data**
- AI data centers: [Epoch AI data centers dataset](https://epoch.ai/data/data-centers-documentation),
  published under a Creative Commons Attribution (CC BY) licence.
  Coordinates were added by geocoding with
  [Nominatim](https://nominatim.org/) (OpenStreetMap data, ODbL) plus manual
  corrections; values are unchanged.
- Country borders: [Natural Earth](https://www.naturalearthdata.com/)
  Admin 0 Countries 1:50m, public domain.
- Map tiles: © [OpenStreetMap](https://www.openstreetmap.org/copyright)
  contributors, ODbL.

**Libraries**
- [Leaflet](https://leafletjs.com/) (BSD 2-Clause),
  [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) (MIT),
  [Bootstrap](https://getbootstrap.com/) (MIT).
- [Django](https://www.djangoproject.com/) (BSD),
  [Django REST Framework](https://www.django-rest-framework.org/) (BSD),
  [djangorestframework-gis](https://github.com/openwisp/django-rest-framework-gis) (MIT),
  [django-filter](https://github.com/carltongibson/django-filter) (BSD),
  [drf-spectacular](https://github.com/tfranzel/drf-spectacular) (BSD),
  [gunicorn](https://gunicorn.org/) (MIT), [psycopg](https://www.psycopg.org/) (LGPL).
- [PostGIS](https://postgis.net/), [Nginx](https://nginx.org/),
  [pgAdmin 4](https://www.pgadmin.org/).
