from pathlib import Path

from django.core.management import call_command

from ai_datacenters.models import Country

FIXTURE = Path(__file__).parent / "fixtures" / "countries_2.geojson"


def test_load_countries_loads_polygons(db):
    call_command("load_countries", str(FIXTURE))

    assert Country.objects.count() == 2
    testland = Country.objects.get(name="Testland")
    assert testland.iso_a3 == "TST"
    # Single polygons are stored as MultiPolygons.
    assert testland.geom.geom_type == "MultiPolygon"
    assert len(Country.objects.get(name="Islandia").geom) == 2


def test_load_countries_twice_is_a_noop(db):
    call_command("load_countries", str(FIXTURE))
    first_ids = set(Country.objects.values_list("id", flat=True))
    call_command("load_countries", str(FIXTURE))
    assert set(Country.objects.values_list("id", flat=True)) == first_ids
