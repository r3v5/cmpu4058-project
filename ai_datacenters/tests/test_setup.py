"""Harness check: tests run against a real PostGIS database, not SQLite."""

import pytest
from django.db import connection


@pytest.mark.django_db
def test_postgis_available():
    with connection.cursor() as cursor:
        cursor.execute("SELECT PostGIS_Version()")
        (version,) = cursor.fetchone()
    assert version
