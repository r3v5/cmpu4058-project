"""HTML pages: the map (login required), sign up, log in and log out."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

VALID_SIGNUP = {"username": "newuser", "password1": "a-Long-pass-829!", "password2": "a-Long-pass-829!"}


@pytest.fixture
def logged_in(client, demo_user):
    client.force_login(demo_user)
    return client


def test_anonymous_map_redirects_to_login(client, db):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/accounts/login/?next=/"


def test_map_page_for_logged_in_user(logged_in):
    response = logged_in.get("/")
    assert response.status_code == 200
    assert "map.html" in [t.name for t in response.templates]
    html = response.content.decode()
    assert 'id="map"' in html
    assert 'id="filters"' in html
    assert 'name="owner"' in html
    assert 'name="search"' in html
    # circle size toggles
    assert "IT Power (MW)" in html and "Capital cost ($B)" in html and "H100e" in html
    assert 'name="h100e_min"' in html and 'name="h100e_max"' in html
    assert "demo" in html  # user name in the navbar


def test_login_page_renders_and_links_to_signup(client, db):
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert 'href="/accounts/signup/"' in response.content.decode()


def test_login_with_wrong_password_shows_message(client, demo_user):
    response = client.post("/accounts/login/", {"username": "demo", "password": "wrong"})
    assert response.status_code == 200
    assert "Username or password is incorrect." in response.content.decode()


def test_login_redirects_to_map(client, demo_user):
    response = client.post("/accounts/login/", {"username": "demo", "password": "demo-pass-123!"})
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_signup_page_renders_form(client, db):
    response = client.get("/accounts/signup/")
    assert response.status_code == 200
    html = response.content.decode()
    assert 'name="username"' in html
    assert 'name="password1"' in html
    assert 'name="password2"' in html
    assert 'href="/accounts/login/"' in html


def test_signup_creates_regular_user_logs_in_and_redirects(client, db):
    response = client.post("/accounts/signup/", VALID_SIGNUP)
    assert response.status_code == 302
    assert response["Location"] == "/"
    user = User.objects.get(username="newuser")
    assert not user.is_staff and not user.is_superuser
    assert client.get("/").status_code == 200  # logged in


@pytest.mark.parametrize(
    "changes, field",
    [
        ({"password2": "something-else-1!"}, "password2"),
        ({"username": "demo"}, "username"),
        ({"password1": "12345678", "password2": "12345678"}, "password2"),
    ],
)
def test_invalid_signup_rerenders_with_errors(client, demo_user, changes, field):
    response = client.post("/accounts/signup/", {**VALID_SIGNUP, **changes})
    assert response.status_code == 200
    assert response.context["form"].errors[field]
    html = response.content.decode()
    assert 'aria-invalid="true"' in html
    assert User.objects.count() == 1  # only demo


@pytest.mark.parametrize("url", ["/accounts/signup/", "/accounts/login/"])
def test_logged_in_user_is_redirected_away_from_auth_pages(logged_in, url):
    response = logged_in.get(url)
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_logout_via_post_ends_session(logged_in):
    response = logged_in.post("/accounts/logout/")
    assert response.status_code == 302
    assert logged_in.get("/").status_code == 302


def test_map_page_explains_each_measure(logged_in):
    html = logged_in.get("/").content.decode()
    # One button next to the size toggles opens a panel with every measure.
    assert 'aria-label="What do these measures mean?"' in html
    assert "can draw at once" in html  # IT power
    assert "build and equip" in html  # capital cost
    assert "Nvidia H100" in html  # H100 equivalents
    # Each range in the filter menu has its own hint, hidden until opened.
    for key in ("power_mw", "capital_cost_busd", "h100e"):
        assert f'aria-controls="help-{key}"' in html
        assert f'id="help-{key}" hidden' in html


def test_size_toggles_have_short_labels_for_phones(logged_in):
    html = logged_in.get("/").content.decode()
    # Phones show the short label; screen readers always get the full one.
    for long, short in (("IT Power (MW)", "MW"), ("Capital cost ($B)", "$B")):
        assert f'<span class="label-long">{long}</span><span class="label-short" aria-hidden="true">{short}</span>' in html
