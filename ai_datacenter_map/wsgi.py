"""WSGI config for ai_datacenter_map project (served by gunicorn)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ai_datacenter_map.settings")

application = get_wsgi_application()
