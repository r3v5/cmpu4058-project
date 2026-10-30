"""Create the two test accounts a grader needs: admin (staff) and demo."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

ACCOUNTS = [
    # username, password env variable, staff + superuser
    ("admin", "SEED_ADMIN_PASSWORD", True),
    ("demo", "SEED_DEMO_PASSWORD", False),
]


class Command(BaseCommand):
    help = "Create the admin and demo accounts if they do not exist yet."

    def handle(self, *args, **options):
        User = get_user_model()
        for username, env_var, is_admin in ACCOUNTS:
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"User '{username}' exists; leaving it unchanged.")
                continue
            password = os.environ.get(env_var)
            if not password:
                raise CommandError(f"Set {env_var} to create the '{username}' account.")
            if is_admin:
                User.objects.create_superuser(username=username, password=password)
            else:
                User.objects.create_user(username=username, password=password)
            self.stdout.write(self.style.SUCCESS(f"Created user '{username}'."))
