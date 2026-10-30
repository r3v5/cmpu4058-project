"""Spatial query endpoints on hand-made Testland data.

Along latitude 1, 0.1 degree of longitude is ~11.13 km and 1 degree ~111.3 km.
"""

import json

import pytest
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point, Polygon

from ai_datacenters.models import Country


@pytest.fixture
def islandia(db):
    square = Polygon(((40, 40), (60, 40), (60, 60), (40, 60), (40, 40)), srid=4326)
    return Country.objects.create(name="Islandia", iso_a3="ISD", geom=MultiPolygon(square, srid=4326))


@pytest.fixture
def sites(testland, islandia, make_dc):
    return {
        "A": make_dc("A", 1.0, 1.0, power_mw=100, capital_cost_busd=1.0),
        "B": make_dc("B", 1.1, 1.0, power_mw=200, capital_cost_busd=2.0),
        "C": make_dc("C", 2.0, 1.0, power_mw=300, capital_cost_busd=3.0),
        "D": make_dc("D", 8.0, 8.0, power_mw=400, capital_cost_busd=4.0),
        "X": make_dc("X", 50.0, 50.0, power_mw=1000, capital_cost_busd=10.0),
    }


def feature_names(collection):
    return [f["properties"]["name"] for f in collection["features"]]


# --- Nearest --------------------------------------------------------------

def test_nearest_returns_sites_in_distance_order_limited_to_n(demo_client, sites):
    response = demo_client.get("/api/datacenters/nearest/", {"lat": 1.0, "lon": 1.02, "n": 3})
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert feature_names(data) == ["A", "B", "C"]
    distances = [f["properties"]["distance_km"] for f in data["features"]]
    assert distances == sorted(distances)
    assert distances[0] == pytest.approx(2.23, abs=0.01)


def test_nearest_includes_line_from_click_to_each_site(demo_client, sites):
    data = demo_client.get("/api/datacenters/nearest/", {"lat": 1.0, "lon": 1.02}).json()
    assert len(data["features"]) == 5  # default n=5
    for feature in data["features"]:
        link = feature["properties"]["link"]
        assert link["type"] == "LineString"
        assert link["coordinates"][0] == [1.02, 1.0]
        assert link["coordinates"][1] == feature["geometry"]["coordinates"]


# --- Within radius --------------------------------------------------------

def test_within_returns_sites_in_radius_and_buffer(demo_client, sites):
    response = demo_client.get("/api/datacenters/within/", {"lat": 1.0, "lon": 1.0, "km": 50})
    assert response.status_code == 200, response.content
    data = response.json()
    assert feature_names(data["sites"]) == ["A", "B"]
    buffer = GEOSGeometry(json.dumps(data["buffer"]))
    assert buffer.geom_type == "Polygon"
    assert buffer.contains(Point(1.4, 1.0))  # ~44 km
    assert not buffer.contains(Point(1.5, 1.0))  # ~56 km


# --- Country at point -----------------------------------------------------

def test_country_at_point_returns_country_and_its_sites(demo_client, sites):
    response = demo_client.get("/api/countries/at/", {"lat": 5, "lon": 5})
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["country"]["properties"]["name"] == "Testland"
    assert data["country"]["geometry"]["type"] == "MultiPolygon"
    assert sorted(feature_names(data["sites"])) == ["A", "B", "C", "D"]
    assert data["country"]["properties"]["site_count"] == 4
    assert data["country"]["properties"]["total_mw"] == 1000


def test_country_at_point_in_ocean_returns_404(demo_client, sites):
    response = demo_client.get("/api/countries/at/", {"lat": 0, "lon": -30})
    assert response.status_code == 404


# --- Country stats --------------------------------------------------------

def test_country_stats_sum_sites_per_country(demo_client, sites):
    response = demo_client.get("/api/countries/stats/")
    assert response.status_code == 200, response.content
    stats = {f["properties"]["name"]: f["properties"] for f in response.json()["features"]}
    assert set(stats) == {"Testland", "Islandia"}
    assert stats["Testland"]["site_count"] == 4
    assert stats["Testland"]["total_mw"] == 1000
    assert stats["Testland"]["total_cost_busd"] == pytest.approx(10.0)
    assert stats["Islandia"]["site_count"] == 1
    assert stats["Islandia"]["total_mw"] == 1000


def test_country_stats_skip_countries_without_sites(demo_client, testland):
    assert demo_client.get("/api/countries/stats/").json()["features"] == []


# --- Validation -----------------------------------------------------------

@pytest.mark.parametrize(
    "url, params, field",
    [
        ("/api/datacenters/nearest/", {"lat": 91, "lon": 0}, "lat"),
        ("/api/datacenters/nearest/", {"lat": 0, "lon": -181}, "lon"),
        ("/api/datacenters/nearest/", {"lat": 0, "lon": 0, "n": 50}, "n"),
        ("/api/datacenters/nearest/", {"lat": 0, "lon": 0, "n": 0}, "n"),
        ("/api/datacenters/nearest/", {"lon": 0}, "lat"),
        ("/api/datacenters/nearest/", {"lat": "abc", "lon": 0}, "lat"),
        ("/api/datacenters/within/", {"lat": 0, "lon": 0, "km": 0}, "km"),
        ("/api/datacenters/within/", {"lat": 0, "lon": 0, "km": 6000}, "km"),
        ("/api/datacenters/within/", {"lat": 0, "lon": 0}, "km"),
        ("/api/countries/at/", {"lat": 91, "lon": 0}, "lat"),
    ],
)
def test_invalid_parameters_return_400_with_field_error(demo_client, url, params, field):
    response = demo_client.get(url, params)
    assert response.status_code == 400
    assert field in response.json()


# --- Buffer edge cases ----------------------------------------------------

@pytest.mark.parametrize(
    "lat, lon, km, inside",
    [
        (0, 179, 500, [(179, 0), (181, 0), (177, 0)]),  # crosses the date line
        (0, -179, 500, [(-179, 0), (-181, 0)]),
        (60, 25, 5000, [(25, 60), (25, 85), (-155, 85)]),  # reaches the North Pole
        (85, 0, 1000, [(0, 85), (179, 89), (-179, 89), (90, 88)]),
        (-80, 0, 2000, [(0, -80), (179, -89)]),  # South Pole
    ],
)
def test_buffer_is_valid_and_continuous(lat, lon, km, inside):
    from ai_datacenters.spatial import buffer_polygon

    buffer = buffer_polygon(Point(lon, lat, srid=4326), km)
    assert buffer.valid
    ring = buffer.coords[0]
    # No jump across ±180: the ring stays around the centre (Leaflet draws
    # longitudes beyond ±180 next to the date line). Only the edge that
    # closes a polar circle along the pole itself may span 360 degrees.
    assert all(
        abs(b[0] - a[0]) < 180
        for a, b in zip(ring, ring[1:])
        if abs(a[1]) != 90 or abs(b[1]) != 90
    )
    for x, y in inside:
        assert buffer.contains(Point(x, y)), (x, y)
