"""Load Natural Earth country polygons into the Country table."""

from django.conf import settings
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import MultiPolygon
from django.core.management.base import BaseCommand
from django.db import transaction

from ai_datacenters.models import Country


class Command(BaseCommand):
    help = "Load country polygons from GeoJSON (skipped if countries exist)."

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", default=str(settings.BASE_DIR / "data" / "countries.geojson"))

    def handle(self, *args, **options):
        if Country.objects.exists():
            self.stdout.write("Countries already loaded; skipping.")
            return

        # Not LayerMapping: the layer mixes Polygon and MultiPolygon features,
        # which GDAL reports as geometry type "Unknown" and LayerMapping rejects.
        layer = DataSource(options["path"])[0]
        countries = []
        for feature in layer:
            geom = feature.geom.geos
            if geom.geom_type == "Polygon":
                geom = MultiPolygon(geom)
            geom.srid = 4326
            countries.append(Country(
                # NAME_LONG matches the Epoch AI country names ("United
                # States", not "United States of America"). ADM0_A3 is used
                # because ISO_A3 is "-99" for some countries (Norway, France).
                name=feature.get("NAME_LONG"),
                iso_a3=feature.get("ADM0_A3"),
                geom=geom,
            ))
        with transaction.atomic():
            Country.objects.bulk_create(countries)
        self.stdout.write(self.style.SUCCESS(f"Loaded {len(countries)} countries."))
