from pathlib import Path

import pytest
from django.core.management import CommandError, call_command

from ai_datacenters.models import DataCenter

FIXTURES = Path(__file__).parent / "fixtures"


def run_import(name, *args):
    call_command("import_datacenters", str(FIXTURES / name), *args)


def test_import_creates_rows_with_points_and_country(testland):
    run_import("datacenters_3.csv")

    assert DataCenter.objects.count() == 3
    alpha = DataCenter.objects.get(name="Alpha")
    assert (alpha.location.x, alpha.location.y) == (1.0, 1.0)
    assert alpha.country == testland
    assert alpha.users == "Anthropic, Cursor"
    assert alpha.power_mw == 946
    assert alpha.geocode_precision == "address"
    # Unknown country names leave the FK empty instead of failing.
    assert DataCenter.objects.get(name="Gamma").country is None


def test_import_is_idempotent(testland):
    run_import("datacenters_3.csv")
    run_import("datacenters_3.csv")
    assert DataCenter.objects.count() == 3


def test_import_computes_nearest_links(testland):
    run_import("datacenters_3.csv")
    alpha = DataCenter.objects.get(name="Alpha")
    assert alpha.nearest_link is not None
    assert alpha.nearest_km == pytest.approx(11.13, abs=0.01)


def test_bad_latitude_is_rejected_with_clear_error(testland):
    with pytest.raises(CommandError, match=r"Broken.*location"):
        run_import("datacenters_bad_lat.csv")
    # The whole import is rolled back.
    assert DataCenter.objects.count() == 0


def test_if_empty_skips_when_table_has_rows(testland, make_dc):
    make_dc("Existing", 5, 5)
    run_import("datacenters_3.csv", "--if-empty")
    assert list(DataCenter.objects.values_list("name", flat=True)) == ["Existing"]
