"""Spatial queries, written with the GeoDjango ORM as in the labs."""

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.gdal import OGRGeometry, SpatialReference
from django.contrib.gis.geos import LineString, Point, Polygon
from django.contrib.gis.measure import D
from django.db.models import (
    Count, Expression, F, Field, FloatField, Func, IntegerField, OuterRef, Q, QuerySet, Subquery, Sum,
)
from django.db.models.functions import Coalesce

from .models import Country, DataCenter

# (min_lon, min_lat, max_lon, max_lat)
BBox = tuple[float, float, float, float]


def recompute_nearest_links():
    """Store, for every site, a line to its closest other site and its length.

    ``Distance`` on a longitude/latitude field measures metres on the Earth's
    surface, so "closest" is a true ground distance, not a difference in
    degrees. ``spheroid=True`` uses the WGS 84 ellipsoid (ST_DistanceSpheroid)
    instead of a perfect sphere, which is accurate to well under 1%.

    Rows are written with ``QuerySet.update()``, which does not call
    ``DataCenter.save()``, so this cannot recurse. The dataset is ~100 rows,
    so recomputing every site is cheap.
    """
    for site in DataCenter.objects.all():
        nearest = (
            DataCenter.objects.exclude(pk=site.pk)
            .annotate(distance=Distance("location", site.location, spheroid=True))
            .order_by("distance")
            .first()
        )
        if nearest is None:
            link, km = None, None
        else:
            link = LineString(site.location, nearest.location, srid=4326)
            km = nearest.distance.km
        DataCenter.objects.filter(pk=site.pk).update(nearest_link=link, nearest_km=km)


def nearest_datacenters(point: Point, n: int, sites: QuerySet[DataCenter] | None = None):
    """Nearest neighbours: the n sites closest to a point, closest first.

    ``sites`` limits the search (e.g. to the filtered list); default all.
    """
    sites = DataCenter.objects.all() if sites is None else sites
    return (
        sites.select_related("country")
        .annotate(distance=Distance("location", point, spheroid=True))
        .order_by("distance")[:n]
    )


def datacenters_within(point: Point, km: float, sites: QuerySet[DataCenter] | None = None):
    """Radius search: sites within km of a point, closest first.

    Two steps. First the boxes around the search circle (``in_bbox``), which
    the GiST index on location answers without reading every row. Then the
    exact distance on the ellipsoid, which PostGIS computes only for the
    sites inside the boxes. ``sites`` limits the search; default all.
    """
    sites = DataCenter.objects.all() if sites is None else sites
    in_boxes = Q()
    for box in _circle_boxes(point, km):
        in_boxes |= Q(location__within=Polygon.from_bbox(box))
    return (
        sites.select_related("country")
        .filter(in_boxes)
        .filter(location__distance_lte=(point, D(km=km), "spheroid"))
        .annotate(distance=Distance("location", point, spheroid=True))
        .order_by("distance")
    )


def in_bbox(queryset: QuerySet[DataCenter], bbox: BBox):
    """Bounding box: sites inside a (min_lon, min_lat, max_lon, max_lat) box.

    Polygon.from_bbox + __within. The GiST index on
    location makes this a fast index lookup, which is what the map needs to
    show only the sites in the current view.
    """
    return queryset.filter(location__within=Polygon.from_bbox(bbox))


def _circle_boxes(point: Point, km: float):
    """Bounding boxes that together cover the circle of radius km.

    Taken from the buffer polygon, drawn 0.1% larger: its straight edges
    cut slightly inside the true circle (by 0.03% of the radius), and a site
    there must not be missed. A circle crossing the date line has
    longitudes beyond ±180, so its box is split into one box on each side.
    """
    min_x, min_y, max_x, max_y = buffer_polygon(point, km * 1.001).extent
    boxes = [(max(min_x, -180), min_y, min(max_x, 180), max_y)]
    if min_x < -180:
        boxes.append((min_x + 360, min_y, 180, max_y))
    if max_x > 180:
        boxes.append((-180, min_y, max_x - 360, max_y))
    return boxes


def buffer_polygon(point: Point, km: float):
    """Buffer: a circle of radius km around a point, as a lon/lat Polygon.

    Buffering in degrees would give an oval that is wrong away from the
    equator, so the circle is drawn in metres in an azimuthal equidistant
    projection centred on the point, then converted back to lon/lat.

    Two cases need care after the conversion:
    - Near the date line, longitudes jump from 180 to -180. They are
      unwrapped (shifted by 360) so the ring stays continuous around the
      point; Leaflet draws longitudes beyond ±180 next to the date line.
    - A circle around a pole cannot close in lon/lat: the unwrapped ring
      ends 360 degrees from where it starts. It becomes a polar cap from
      -180 to 180, closed along the pole.
    """
    local = SpatialReference(f"+proj=aeqd +lat_0={point.y} +lon_0={point.x} +datum=WGS84 +units=m")
    circle = OGRGeometry(Point(0, 0).buffer(km * 1000, quadsegs=32).wkt, srs=local)
    circle.transform(SpatialReference(4326))

    ring = []
    previous_x = point.x
    for x, y in circle.geos.coords[0]:
        x += 360 * round((previous_x - x) / 360)
        ring.append((x, y))
        previous_x = x
    if abs(ring[-1][0] - ring[0][0]) > 180:
        ring = _polar_cap(ring[:-1], pole=90 if point.y > 0 else -90)
    return Polygon(ring, srid=4326)


def _polar_cap(vertices: list[tuple[float, float]], pole: float):
    """Turn a ring that winds around a pole into a closed lon/lat polygon."""
    edge = sorted(((x + 180) % 360 - 180, y) for x, y in vertices)
    # Latitude where the ring crosses the date line, between the last and
    # the first vertex.
    (last_x, last_y), (first_x, first_y) = edge[-1], edge[0]
    t = (180 - last_x) / (first_x + 360 - last_x)
    seam_y = last_y + t * (first_y - last_y)
    return [(-180, seam_y), *edge, (180, seam_y), (180, pole), (-180, pole), (-180, seam_y)]


def country_at(point: Point):
    """Containment: the country polygon containing a point, or None."""
    return Country.objects.filter(geom__contains=point).first()


def datacenters_in(country: Country, sites: QuerySet[DataCenter] | None = None):
    """Containment: sites located inside a country polygon."""
    sites = DataCenter.objects.all() if sites is None else sites
    return sites.select_related("country").filter(location__within=country.geom)


def _sites_inside(expression: Expression, output_field: Field):
    """A subquery aggregating the sites inside the outer country's polygon.

    ``Func`` rather than ``Count``/``Sum`` so Django does not add GROUP BY:
    the subquery returns one row per country.
    """
    sites = DataCenter.objects.filter(location__within=OuterRef("geom")).order_by()
    return Subquery(sites.annotate(value=expression).values("value"), output_field=output_field)


def country_stats():
    """Spatial join + aggregate: totals per country, by point-in-polygon.

    Joins on geometry (location within geom), not on the country foreign
    key, so the result comes straight from the spatial relationship.
    """
    count = Func(F("id"), function="COUNT")
    total_mw = Coalesce(Func(F("power_mw"), function="SUM"), 0.0, output_field=FloatField())
    total_cost = Coalesce(Func(F("capital_cost_busd"), function="SUM"), 0.0, output_field=FloatField())
    return (
        Country.objects.annotate(
            site_count=_sites_inside(count, IntegerField()),
            total_mw=_sites_inside(total_mw, FloatField()),
            total_cost_busd=_sites_inside(total_cost, FloatField()),
        )
        .filter(site_count__gt=0)
        .order_by("-total_mw")
    )


def country_totals(sites: QuerySet[DataCenter]):
    """Count, MW and cost of a queryset of sites."""
    return sites.aggregate(
        site_count=Count("id"),
        total_mw=Coalesce(Sum("power_mw"), 0.0),
        total_cost_busd=Coalesce(Sum("capital_cost_busd"), 0.0),
    )
