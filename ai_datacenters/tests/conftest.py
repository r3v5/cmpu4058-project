"""Shared fixtures: tiny hand-made geometries with obvious expected results.

"Testland" is a 10 x 10 degree square on the equator. Points A and B are
0.1 degrees of longitude apart (about 11.13 km); C is far away.
"""

import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon

from ai_datacenters.models import Country, DataCenter


@pytest.fixture(autouse=True)
def plain_static_storage(settings):
    """Tests do not run collectstatic, so there is no hashed-name manifest."""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def testland(db):
    square = Polygon(((0, 0), (10, 0), (10, 10), (0, 10), (0, 0)), srid=4326)
    return Country.objects.create(name="Testland", iso_a3="TST", geom=MultiPolygon(square, srid=4326))


@pytest.fixture
def make_dc(db):
    """Create a DataCenter with sensible defaults; override any field."""

    def make(name, lon, lat, **fields):
        defaults = {
            "owner": "Google",
            "power_mw": 100,
            "capital_cost_busd": 1.0,
            "h100e": 50000,
            "geocode_precision": DataCenter.Precision.ADDRESS,
        }
        defaults.update(fields)
        return DataCenter.objects.create(name=name, location=Point(lon, lat, srid=4326), **defaults)

    return make


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def demo_user(django_user_model):
    return django_user_model.objects.create_user(username="demo", password="demo-pass-123!")


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(
        username="admin", password="admin-pass-123!", is_staff=True
    )


@pytest.fixture
def demo_client(api_client, demo_user):
    api_client.force_authenticate(demo_user)
    return api_client


@pytest.fixture
def staff_client(api_client, staff_user):
    api_client.force_authenticate(staff_user)
    return api_client
