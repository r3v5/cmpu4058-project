"""Geocoding helpers are pure functions; Nominatim is replaced by a fake."""

from ai_datacenters.geocoding import candidates, clean_owner, clean_tag, geocode_row, load_overrides


def row(**fields):
    base = {"Name": "Site", "Country": "United States", "Address": ""}
    base.update(fields)
    return base


def test_clean_tag_strips_confidence_tag():
    assert clean_tag("Google #confident") == "Google"


def test_clean_tag_cleans_every_item_of_a_list():
    assert clean_tag("Anthropic #confident, Cursor #likely") == "Anthropic, Cursor"


def test_empty_owner_becomes_unknown():
    assert clean_owner("") == "Unknown"
    assert clean_owner("  ") == "Unknown"
    assert clean_owner("Meta #confident") == "Meta"


def test_candidates_follow_fallback_order():
    r = row(Address="5420 Tulane Rd, Memphis, TN 38109")
    assert list(candidates(r)) == [
        ("address", {"q": "5420 Tulane Rd, Memphis, TN 38109"}),
        ("city", {"q": "Memphis, TN 38109"}),
        ("postcode", {"postalcode": "38109", "countrycodes": "us"}),
        ("city", {"q": "Memphis, United States"}),
        ("country", {"q": "United States"}),
    ]


def test_candidates_without_address_only_try_country():
    assert list(candidates(row(Country="Malaysia"))) == [("country", {"q": "Malaysia"})]


def test_candidates_skip_zip_outside_united_states():
    r = row(Country="Malaysia", Address="Jalan 1, 81300 Johor Bahru, Johor, Malaysia")
    assert all(precision != "postcode" for precision, _ in candidates(r))


def test_geocoder_stops_at_first_hit_and_records_precision():
    calls = []

    def fake_search(params):
        calls.append(params)
        return (35.0, -90.0) if len(calls) == 2 else None

    r = row(Address="5420 Tulane Rd, Memphis, TN 38109")
    assert geocode_row(r, fake_search, overrides={}) == (35.0, -90.0, "city")
    assert len(calls) == 2


def test_override_wins_and_sets_manual_precision(tmp_path):
    path = tmp_path / "overrides.csv"
    path.write_text("name,latitude,longitude,note\nSite,1.5,103.6,Nusajaya Tech Park\n")

    def fail_search(params):
        raise AssertionError("Nominatim must not be called for overridden rows")

    assert geocode_row(row(), fail_search, overrides=load_overrides(path)) == (1.5, 103.6, "manual")


def test_no_hit_returns_none():
    assert geocode_row(row(), lambda params: None, overrides={}) is None
