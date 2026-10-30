"""GET /api/datacenters/ — GeoJSON list with filters."""

import pytest

URL = "/api/datacenters/"


@pytest.fixture
def sites(testland, make_dc):
    make_dc("Alpha", 1, 1, owner="Google", power_mw=100, capital_cost_busd=1.0)
    make_dc("Beta", 2, 2, owner="Meta", power_mw=200, capital_cost_busd=2.0)
    make_dc("Gamma", 3, 3, owner="Amazon", power_mw=300, capital_cost_busd=3.0)
    make_dc("Faraway", 50, 50, owner="Google", power_mw=400, capital_cost_busd=4.0)


def names(response):
    assert response.status_code == 200, response.content
    return sorted(f["properties"]["name"] for f in response.json()["features"])


def test_list_is_geojson_feature_collection(demo_client, sites):
    data = demo_client.get(URL).json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 4
    alpha = next(f for f in data["features"] if f["properties"]["name"] == "Alpha")
    assert alpha["geometry"] == {"type": "Point", "coordinates": [1.0, 1.0]}
    assert alpha["properties"]["country"] == "Testland"
    assert alpha["properties"]["owner"] == "Google"
    # The stored nearest-site line is included for the "cluster links" layer.
    assert alpha["properties"]["nearest_link"]["type"] == "LineString"
    assert alpha["properties"]["nearest_km"] > 0


def test_filter_by_owner(demo_client, sites):
    assert names(demo_client.get(URL, {"owner": "Google"})) == ["Alpha", "Faraway"]


def test_filter_by_several_owners(demo_client, sites):
    assert names(demo_client.get(URL, {"owner": ["Google", "Meta"]})) == ["Alpha", "Beta", "Faraway"]


def test_filter_by_country(demo_client, sites):
    assert names(demo_client.get(URL, {"country": "Testland"})) == ["Alpha", "Beta", "Gamma"]


@pytest.mark.parametrize(
    "params, expected",
    [
        ({"mw_min": 200}, ["Beta", "Faraway", "Gamma"]),
        ({"mw_max": 200}, ["Alpha", "Beta"]),
        ({"cost_min": 3}, ["Faraway", "Gamma"]),
        ({"cost_max": 3}, ["Alpha", "Beta", "Gamma"]),
    ],
)
def test_range_boundaries_are_inclusive(demo_client, sites, params, expected):
    assert names(demo_client.get(URL, params)) == expected


def test_combined_filters(demo_client, sites):
    params = {"owner": "Google", "country": "Testland", "mw_min": 50}
    assert names(demo_client.get(URL, params)) == ["Alpha"]


def test_non_numeric_filter_returns_400(demo_client, sites):
    response = demo_client.get(URL, {"mw_min": "abc"})
    assert response.status_code == 400
    assert "mw_min" in response.json()


def test_filter_options(demo_client, sites):
    data = demo_client.get("/api/filters/").json()
    assert data["owners"] == ["Amazon", "Google", "Meta"]
    assert data["countries"] == ["Testland"]
    assert data["power_mw"] == {"min": 100, "max": 400}
    assert data["capital_cost_busd"] == {"min": 1.0, "max": 4.0}
