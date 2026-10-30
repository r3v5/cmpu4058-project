#!/bin/sh
# Prepare the database and static files, then start the main process (gunicorn).
set -e

echo "Waiting for the database..."
attempt=1
until python manage.py shell -c "from django.db import connection; connection.ensure_connection()" >/dev/null 2>/tmp/db_check.err; do
  if [ "$attempt" -ge 30 ]; then
    # Settings errors also end up here, so show the real cause.
    echo "Database not reachable after $attempt attempts. Last error:" >&2
    cat /tmp/db_check.err >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 1
done

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py load_countries
# --if-empty: keep edits made in the admin or API across restarts.
python manage.py import_datacenters --if-empty
python manage.py seed_users

exec "$@"
