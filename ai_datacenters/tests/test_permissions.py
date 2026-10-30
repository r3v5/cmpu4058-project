"""Reads need a login; writes need a staff account."""

import pytest
from rest_framework.authtoken.models import Token

from ai_datacenters.models import DataCenter

URL = "/api/datacenters/"


def feature(**properties):
    base = {
        "name": "New Site",
        "owner": "Google",
        "power_mw": 50,
        "capital_cost_busd": 1.5,
        "geocode_precision": "manual",
    }
    base.update(properties)
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [3, 3]}, "properties": base}


@pytest.mark.parametrize(
    "url", [URL, "/api/datacenters/nearest/?lat=0&lon=0", "/api/countries/stats/", "/api/filters/"]
)
def test_anonymous_requests_are_rejected(api_client, db, url):
    assert api_client.get(url).status_code in (401, 403)


def test_regular_user_can_read(demo_client, make_dc):
    dc = make_dc("Alpha", 1, 1)
    assert demo_client.get(URL).status_code == 200
    assert demo_client.get(f"{URL}{dc.pk}/").status_code == 200


def test_regular_user_cannot_write(demo_client, make_dc):
    dc = make_dc("Alpha", 1, 1)
    assert demo_client.post(URL, feature(), format="json").status_code == 403
    assert demo_client.patch(f"{URL}{dc.pk}/", {"properties": {"owner": "X"}}, format="json").status_code == 403
    assert demo_client.delete(f"{URL}{dc.pk}/").status_code == 403
    assert DataCenter.objects.count() == 1


def test_staff_can_create_update_and_delete(staff_client, testland):
    response = staff_client.post(URL, feature(), format="json")
    assert response.status_code == 201, response.content
    pk = response.json()["id"]
    created = DataCenter.objects.get(pk=pk)
    assert (created.location.x, created.location.y) == (3, 3)
    assert created.country == testland  # set from the polygon, not the request

    response = staff_client.patch(
        f"{URL}{pk}/", {"type": "Feature", "properties": {"owner": "Meta"}}, format="json"
    )
    assert response.status_code == 200, response.content
    assert DataCenter.objects.get(pk=pk).owner == "Meta"

    assert staff_client.delete(f"{URL}{pk}/").status_code == 204
    assert not DataCenter.objects.filter(pk=pk).exists()


@pytest.mark.parametrize(
    "payload, field",
    [
        ({**feature(), "geometry": {"type": "Point", "coordinates": "nonsense"}}, "location"),
        ({**feature(), "geometry": {"type": "Point", "coordinates": [0, 95]}}, "location"),
        (feature(power_mw=-5), "power_mw"),
        (feature(geocode_precision="country"), "geocode_precision"),
    ],
)
def test_invalid_create_returns_400(staff_client, db, payload, field):
    response = staff_client.post(URL, payload, format="json")
    assert response.status_code == 400
    assert field in response.json()
    assert DataCenter.objects.count() == 0


def test_token_authentication_allows_get(api_client, demo_user):
    token = Token.objects.create(user=demo_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    assert api_client.get(URL).status_code == 200


def test_obtain_token_with_username_and_password(api_client, demo_user):
    response = api_client.post("/api/token/", {"username": "demo", "password": "demo-pass-123!"})
    assert response.status_code == 200
    assert response.json()["token"] == Token.objects.get(user=demo_user).key


def test_api_schema_is_served(demo_client):
    assert demo_client.get("/api/schema/").status_code == 200


@pytest.mark.parametrize("url", ["/api/schema/", "/api/docs/"])
def test_api_docs_need_login(api_client, db, url):
    assert api_client.get(url).status_code in (401, 403)
