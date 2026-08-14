#!/bin/sh
set -e

# Railway starts the database service alongside the web service, so the first
# connection can lose the race. Retry briefly instead of crash-looping.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    attempt=1
    max_attempts="${MIGRATE_MAX_ATTEMPTS:-10}"
    until python manage.py migrate --noinput; do
        if [ "$attempt" -ge "$max_attempts" ]; then
            echo "[entrypoint] migrations failed after ${max_attempts} attempts" >&2
            exit 1
        fi
        echo "[entrypoint] database not ready (attempt ${attempt}/${max_attempts}); retrying in 3s" >&2
        attempt=$((attempt + 1))
        sleep 3
    done
fi

# Optional one-shot admin bootstrap: set all three vars to create a superuser.
if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    python manage.py createsuperuser --noinput || true
fi

exec "$@"
