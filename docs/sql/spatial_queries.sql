-- Spatial queries of the AI Data Center Map, as plain PostGIS SQL.
--
-- The app runs the same queries through the GeoDjango ORM
--
-- Tables: ai_datacenters_datacenter (points + lines), ai_datacenters_country
-- (polygons). All geometries are SRID 4326 (longitude/latitude, WGS 84).
-- The example point is Dallas, Texas: longitude -96.80, latitude 32.78.


-- 0. Spatial indexes ------------------------------------------------------
-- Django creates a GiST index on every geometry column.
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename LIKE 'ai_datacenters_%' AND indexdef ILIKE '%USING gist%'
ORDER BY tablename, indexname;


-- 1. Nearest neighbours (spatial.nearest_datacenters, GET /api/datacenters/nearest/)
-- "<->" is the index-assisted KNN operator: the GiST index returns the
-- closest points first. The distance shown is metres on the WGS 84
-- ellipsoid, like Distance(..., spheroid=True) in Django. The line from the
-- point to each site is what the map draws as a dashed line.
SELECT d.name,
       d.owner,
       round((ST_DistanceSpheroid(d.location, p.geom) / 1000)::numeric, 1) AS distance_km,
       ST_MakeLine(p.geom, d.location) AS link
FROM ai_datacenters_datacenter d,
     (SELECT ST_SetSRID(ST_MakePoint(-96.80, 32.78), 4326) AS geom) p
ORDER BY d.location <-> p.geom
LIMIT 5;


-- 2. Radius search + buffer (spatial.datacenters_within / buffer_polygon,
--    GET /api/datacenters/within/)
-- Sites within 500 km, in two steps like the app. ST_Within on the box
-- around the circle uses the GiST index; the exact distance on the WGS 84
-- ellipsoid then runs only for the sites inside the box. (The app takes
-- the box from its buffer circle, 0.1% larger, and splits it in two when
-- the circle crosses the date line.)
SELECT d.name,
       round((ST_DistanceSpheroid(d.location, p.geom) / 1000)::numeric, 1) AS distance_km
FROM ai_datacenters_datacenter d,
     (SELECT ST_SetSRID(ST_MakePoint(-96.80, 32.78), 4326) AS geom) p
WHERE ST_Within(d.location, ST_MakeEnvelope(-102.14, 28.27, -91.46, 37.29, 4326))
  AND ST_DistanceSpheroid(d.location, p.geom) <= 500000
ORDER BY distance_km;

-- The 500 km circle itself as a polygon.

SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(-96.80, 32.78), 4326)::geography, 500000)::geometry AS buffer_500km;


-- 3. Containment (spatial.country_at / datacenters_in, GET /api/countries/at/)
-- The country polygon that contains the point, then the sites inside it.
SELECT c.name, c.iso_a3, c.geom
FROM ai_datacenters_country c
WHERE ST_Contains(c.geom, ST_SetSRID(ST_MakePoint(-96.80, 32.78), 4326));

SELECT d.name, d.owner, d.power_mw
FROM ai_datacenters_datacenter d
JOIN ai_datacenters_country c ON ST_Within(d.location, c.geom)
WHERE c.name = 'United States'
ORDER BY d.power_mw DESC;


-- 4. Spatial join + aggregate (spatial.country_stats, GET /api/countries/stats/)
-- Totals per country, joined on geometry (point in polygon), not on the
-- country foreign key. This feeds the choropleth.
SELECT c.name,
       count(d.id)                     AS site_count,
       round(sum(d.power_mw)::numeric) AS total_mw,
       round(sum(d.capital_cost_busd)::numeric, 1) AS total_cost_busd
FROM ai_datacenters_country c
JOIN ai_datacenters_datacenter d ON ST_Within(d.location, c.geom)
GROUP BY c.name
ORDER BY total_mw DESC;


-- 5. Bounding box (spatial.in_bbox, GET /api/datacenters/?bbox=)
-- "Only sites in map view": the sites inside the visible map rectangle.
-- Here: the eastern United States.
SELECT d.name, ST_AsText(d.location) AS location
FROM ai_datacenters_datacenter d
WHERE ST_Within(d.location, ST_MakeEnvelope(-90, 30, -70, 45, 4326))
ORDER BY d.name;

-- The plan shows the GiST index on location doing the work. (The table is
-- small, so the planner may still pick a sequential scan; SET
-- enable_seqscan = off for this session shows the index plan.)
EXPLAIN
SELECT d.name
FROM ai_datacenters_datacenter d
WHERE ST_Within(d.location, ST_MakeEnvelope(-90, 30, -70, 45, 4326));


-- 6. Stored lines: nearest other site (spatial.recompute_nearest_links)
-- Each site stores a LineString to its closest other site and the length.
-- The app runs this after every save or delete. LATERAL runs the KNN
-- subquery once per site. Wrapped in a transaction that is rolled back, so
-- running it here changes nothing; the app has already stored these values.
BEGIN;
UPDATE ai_datacenters_datacenter a
SET nearest_link = ST_MakeLine(a.location, n.location),
    nearest_km   = ST_DistanceSpheroid(a.location, n.location) / 1000
FROM ai_datacenters_datacenter a2
CROSS JOIN LATERAL (
    SELECT b.location
    FROM ai_datacenters_datacenter b
    WHERE b.id <> a2.id
    ORDER BY b.location <-> a2.location
    LIMIT 1
) n
WHERE a.id = a2.id;
ROLLBACK;

-- The stored lines, shortest first: the most tightly clustered sites.
SELECT name, round(nearest_km::numeric, 1) AS nearest_km, nearest_link
FROM ai_datacenters_datacenter
WHERE nearest_link IS NOT NULL
ORDER BY nearest_km
LIMIT 10;
