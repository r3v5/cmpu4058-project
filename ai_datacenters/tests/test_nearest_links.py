"""nearest_link: a stored LineString from each site to its closest other site."""

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from ai_datacenters.models import DataCenter
from ai_datacenters.spatial import recompute_nearest_links

AB_KM = 11.13  # 0.1 degree of longitude at latitude 1


@pytest.fixture
def abc(make_dc):
    a = make_dc("A", 1.0, 1.0)
    b = make_dc("B", 1.1, 1.0)
    c = make_dc("C", 8.0, 8.0)
    return a, b, c


def reload(*sites):
    for s in sites:
        s.refresh_from_db()


def test_link_is_two_point_line_to_nearest_site(abc):
    a, b, c = abc
    recompute_nearest_links()
    reload(a)
    assert a.nearest_link.geom_type == "LineString"
    assert list(a.nearest_link.coords) == [(1.0, 1.0), (1.1, 1.0)]
    assert a.nearest_km == pytest.approx(AB_KM, abs=0.01)


def test_far_site_links_to_its_nearest_neighbour(abc):
    a, b, c = abc
    reload(c)
    # B is closer to C than A is.
    assert c.nearest_link.coords[-1] == (1.1, 1.0)


def test_nearest_uses_true_distance_not_degrees(make_dc):
    # At latitude 60 a degree of longitude is half a degree of latitude, so
    # E is nearer in degrees (9 vs 10) but D is nearer on the ground.
    o = make_dc("O", 0, 60)
    make_dc("D", 10, 60)
    make_dc("E", 0, 51)
    reload(o)
    assert o.nearest_link.coords[-1] == (10.0, 60.0)


def test_single_site_has_no_link(make_dc):
    a = make_dc("A", 1, 1)
    reload(a)
    assert a.nearest_link is None
    assert a.nearest_km is None


def test_moving_a_site_updates_links(abc):
    a, b, c = abc
    b.location = Point(7.9, 8.0, srid=4326)
    b.save()
    reload(a)
    assert a.nearest_link.coords[-1] == (7.9, 8.0)


def test_deleting_a_site_updates_links(abc):
    a, b, c = abc
    b.delete()
    reload(a)
    assert a.nearest_link.coords[-1] == (8.0, 8.0)


def test_admin_bulk_delete_updates_links(abc, admin_client):
    a, b, c = abc
    response = admin_client.post(
        reverse("admin:ai_datacenters_datacenter_changelist"),
        {"action": "delete_selected", "_selected_action": [b.pk], "post": "yes"},
    )
    assert response.status_code == 302
    assert not DataCenter.objects.filter(pk=b.pk).exists()
    reload(a)
    assert a.nearest_link.coords[-1] == (8.0, 8.0)
