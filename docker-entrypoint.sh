#!/bin/sh
set -e

# Vercel containers autoscale and scale to zero, so migrating on start would
# run on every cold start - repeatedly, possibly concurrently, and adding
# latency to each one. Default to off there and migrate out of band instead;
# on a long-running host migrating on boot is the convenient behaviour.
if [ -n "${VERCEL}" ]; then
    RUN_MIGRATIONS="${RUN_MIGRATIONS:-0}"
else
    RUN_MIGRATIONS="${RUN_MIGRATIONS:-1}"
fi

# A freshly started database can refuse the first connection, so retry briefly
# instead of crash-looping.
if [ "${RUN_MIGRATIONS}" = "1" ]; then
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
