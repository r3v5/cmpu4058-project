"""Spatial queries, written with the GeoDjango ORM as in the labs."""

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import LineString

from .models import DataCenter


def recompute_nearest_links():
    """Store, for every site, a line to its closest other site and its length.

    ``Distance`` on a longitude/latitude field measures metres on the Earth's
    surface, so "closest" is a true ground distance, not a difference in
    degrees. ``spheroid=True`` uses the WGS 84 ellipsoid (ST_DistanceSpheroid)
    instead of a perfect sphere, which is accurate to well under 1%.
    
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
