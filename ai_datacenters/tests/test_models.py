import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.gis.geos import Point

from ai_datacenters.models import DataCenter


def test_datacenter_saves_with_point(make_dc):
    dc = make_dc("Alpha", 1, 1)
    dc.refresh_from_db()
    assert (dc.location.x, dc.location.y) == (1, 1)
    assert dc.location.srid == 4326


@pytest.mark.parametrize("field", ["power_mw", "capital_cost_busd"])
def test_negative_values_fail_validation(make_dc, field):
    dc = make_dc("Alpha", 1, 1)
    setattr(dc, field, -1)
    with pytest.raises(ValidationError) as exc:
        dc.full_clean()
    assert field in exc.value.message_dict


def test_latitude_out_of_range_fails_validation(make_dc):
    dc = make_dc("Alpha", 1, 1)
    dc.location = Point(1, 91, srid=4326)
    with pytest.raises(ValidationError) as exc:
        dc.full_clean()
    assert "location" in exc.value.message_dict


def test_duplicate_name_raises_integrity_error(make_dc):
    make_dc("Alpha", 1, 1)
    with pytest.raises(IntegrityError):
        make_dc("Alpha", 2, 2)


def test_str_returns_name(make_dc):
    assert str(make_dc("Alpha", 1, 1)) == "Alpha"


def test_country_str_returns_name(testland):
    assert str(testland) == "Testland"


def test_country_is_set_from_the_polygon_containing_the_site(testland, make_dc):
    assert make_dc("Inside", 5, 5).country == testland
    assert make_dc("Outside", 50, 50).country is None


def test_moving_a_site_updates_its_country(testland, make_dc):
    dc = make_dc("Mover", 5, 5)
    dc.location = Point(50, 50, srid=4326)
    dc.save()
    dc.refresh_from_db()
    assert dc.country is None
