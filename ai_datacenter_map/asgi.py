"""ASGI config for ai_datacenter_map project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ai_datacenter_map.settings")

application = get_asgi_application()
