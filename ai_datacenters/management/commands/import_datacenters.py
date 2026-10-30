"""Load data/datacenters_geocoded.csv into the DataCenter table.

Idempotent: rows are matched by name and updated in place. The whole file
is imported in one transaction, so one bad row leaves the table unchanged.
"""

import csv

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ai_datacenters.models import DataCenter


class Command(BaseCommand):
    help = "Import geocoded AI data centers from CSV (update or create by name)."

    def add_arguments(self, parser):
        parser.add_argument(
            "path", nargs="?", default=str(settings.BASE_DIR / "data" / "datacenters_geocoded.csv")
        )
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Do nothing when data centers already exist (used at container start, "
            "so edits made in the admin or API are not overwritten).",
        )

    def handle(self, *args, **options):
        if options["if_empty"] and DataCenter.objects.exists():
            self.stdout.write("Data centers already loaded; skipping import.")
            return

        with open(options["path"], newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        with transaction.atomic():
            for line, row in enumerate(rows, start=2):
                self.import_row(line, row)

        outside = DataCenter.objects.filter(country=None).values_list("name", flat=True)
        if outside:
            self.stderr.write(self.style.WARNING(f"Not inside any country polygon: {', '.join(outside)}"))
        self.stdout.write(self.style.SUCCESS(f"Imported {len(rows)} data centers."))

    def import_row(self, line, row):
        name = row["name"].strip()
        try:
            location = Point(float(row["longitude"]), float(row["latitude"]), srid=4326)
            power_mw = float(row["power_mw"])
            cost = float(row["capital_cost_busd"])
        except ValueError as exc:
            raise CommandError(f"Line {line} ({name}): {exc}") from exc

        dc = DataCenter.objects.filter(name=name).first() or DataCenter(name=name)
        dc.owner = row["owner"].strip() or "Unknown"
        dc.users = row["users"].strip()
        dc.power_mw = power_mw
        dc.capital_cost_busd = cost
        dc.address = row["address"].strip()
        dc.location = location
        dc.geocode_precision = row["geocode_precision"].strip()
        try:
            dc.full_clean()
        except ValidationError as exc:
            raise CommandError(f"Line {line} ({name}): {exc.message_dict}") from exc
        # save() also sets the country from the polygon containing the point
        # (the CSV "country" column is kept for reference only) and refreshes
        # every site's nearest link.
        dc.save()
