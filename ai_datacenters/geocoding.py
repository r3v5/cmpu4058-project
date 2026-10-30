"""Turn Epoch AI rows into coordinates with a Nominatim fallback chain.

The functions here are pure (the search function is passed in), so they
are tested without network access. ``geocode_datacenters`` wires them to
the real Nominatim API.
"""

import csv
import re
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ai-datacenter-map-ca1 (student project)"
# Nominatim usage policy: at most one request per second.
REQUEST_SPACING_S = 1.1

_TAG = re.compile(r"\s*#\w+")
_US_ZIP = re.compile(r"\b(\d{5})\b(?!.*\b\d{5}\b)")


def clean_tag(value):
    """Drop Epoch AI confidence tags: 'Google #confident' -> 'Google'."""
    return _TAG.sub("", value or "").strip()


def clean_owner(value):
    return clean_tag(value) or "Unknown"


def candidates(row):
    """Yield (precision, Nominatim params) from most to least precise.

    Order: full address, address without the street, US ZIP code,
    town + country, country.
    """
    address = row["Address"].strip()
    country = row["Country"].strip()
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if address:
        yield "address", {"q": address}
        if len(parts) > 1:
            yield "city", {"q": ", ".join(parts[1:])}
        zip_code = _US_ZIP.search(address)
        if zip_code and country == "United States":
            yield "postcode", {"postalcode": zip_code.group(1), "countrycodes": "us"}
        if len(parts) > 1:
            yield "city", {"q": f"{parts[-2]}, {country}"}
    yield "country", {"q": country}


def load_overrides(path):
    """Read manual coordinates keyed by site name."""
    with open(path, newline="", encoding="utf-8") as f:
        return {r["name"]: (float(r["latitude"]), float(r["longitude"])) for r in csv.DictReader(f)}


def geocode_row(row, search, overrides):
    """Return (lat, lon, precision) for a row, or None when nothing matched.

    A manual override wins. Otherwise the first candidate that ``search``
    resolves is used, and its precision is recorded.
    """
    if row["Name"] in overrides:
        lat, lon = overrides[row["Name"]]
        return lat, lon, "manual"
    for precision, params in candidates(row):
        hit = search(params)
        if hit:
            return hit[0], hit[1], precision
    return None


def nominatim_search(params, session=None):
    """Query Nominatim once; return (lat, lon) of the best hit or None."""
    session = session or requests
    time.sleep(REQUEST_SPACING_S)
    response = session.get(
        NOMINATIM_URL,
        params={**params, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    hits = response.json()
    return (float(hits[0]["lat"]), float(hits[0]["lon"])) if hits else None
