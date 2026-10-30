import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

User = get_user_model()


@pytest.fixture
def seed_env(monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "admin-pass-123!")
    monkeypatch.setenv("SEED_DEMO_PASSWORD", "demo-pass-123!")


def test_seed_users_creates_admin_and_demo(db, seed_env):
    call_command("seed_users")

    admin = User.objects.get(username="admin")
    demo = User.objects.get(username="demo")
    assert admin.is_staff and admin.is_superuser
    assert not demo.is_staff and not demo.is_superuser
    assert admin.check_password("admin-pass-123!")
    assert demo.check_password("demo-pass-123!")


def test_seed_users_twice_is_a_noop(db, seed_env, monkeypatch):
    call_command("seed_users")
    monkeypatch.setenv("SEED_DEMO_PASSWORD", "changed-pass-456!")
    call_command("seed_users")

    assert User.objects.count() == 2
    # Existing accounts are left alone, including their passwords.
    assert User.objects.get(username="demo").check_password("demo-pass-123!")


def test_seed_users_requires_passwords(db, monkeypatch):
    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_DEMO_PASSWORD", raising=False)
    with pytest.raises(CommandError, match="SEED_ADMIN_PASSWORD"):
        call_command("seed_users")
