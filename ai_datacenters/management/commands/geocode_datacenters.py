"""Dev-only: geocode the Epoch AI CSV and write data/datacenters_geocoded.csv.

Needs network access and takes a few minutes (Nominatim allows one request
per second). The output is committed, so Docker startup never runs this.
"""

import csv
import io

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from ai_datacenters.geocoding import clean_owner, clean_tag, geocode_row, load_overrides, nominatim_search

EPOCH_CSV_URL = "https://epoch.ai/data/data_centers/data_centers.csv"
OUTPUT_FIELDS = [
    "name", "owner", "users", "country", "power_mw", "capital_cost_busd",
    "address", "latitude", "longitude", "geocode_precision",
]


class Command(BaseCommand):
    help = "Geocode the Epoch AI data center CSV with Nominatim (needs network)."

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--source", default=EPOCH_CSV_URL, help="URL or path of the Epoch AI CSV.")
        parser.add_argument("--overrides", default=str(settings.BASE_DIR / "data" / "geocode_overrides.csv"))
        parser.add_argument("--out", default=str(settings.BASE_DIR / "data" / "datacenters_geocoded.csv"))

    def handle(self, *args, **options):
        rows = self.read_source(options["source"])
        overrides = load_overrides(options["overrides"])
        session = requests.Session()
        search = lambda params: nominatim_search(params, session)  # noqa: E731

        output, unplaced = [], []
        for row in rows:
            result = geocode_row(row, search, overrides)
            if result is None or result[2] == "country":
                # Country centroids are too vague to map; add an override.
                unplaced.append(row["Name"])
                continue
            lat, lon, precision = result
            output.append({
                "name": row["Name"].strip(),
                "owner": clean_owner(row["Owner"]),
                "users": clean_tag(row["Users"]),
                "country": row["Country"].strip(),
                "power_mw": row["Current power (MW)"],
                "capital_cost_busd": row["Current total capital cost (2025 USD billions)"],
                "address": row["Address"].strip(),
                "latitude": f"{lat:.6f}",
                "longitude": f"{lon:.6f}",
                "geocode_precision": precision,
            })
            self.stdout.write(f"{precision:8} {row['Name']}")

        with open(options["out"], "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            writer.writerows(output)

        self.stdout.write(self.style.SUCCESS(f"Wrote {len(output)} rows to {options['out']}"))
        if unplaced:
            self.stderr.write(self.style.WARNING(
                f"{len(unplaced)} rows only matched a country; add them to the overrides file: "
                + "; ".join(unplaced)
            ))

    def read_source(self, source: str):
        if source.startswith(("http://", "https://")):
            response = requests.get(source, timeout=30)
            response.raise_for_status()
            text = response.content.decode("utf-8-sig")
        else:
            with open(source, encoding="utf-8-sig") as f:
                text = f.read()
        return list(csv.DictReader(io.StringIO(text)))
