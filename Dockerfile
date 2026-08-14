# syntax=docker/dockerfile:1

# The deployable website is the Django project in dashboard_ui/. The computer
# vision scripts at the repository root are not part of the web service and are
# deliberately left out of the image (see .dockerignore).

# ---------------------------------------------------------------------------
# Stage 1: build the virtualenv. The database drivers need a compiler and the
# client headers, but only while they are being built.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        libpq-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY dashboard_ui/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: runtime. Only the shared client libraries are needed to *run* the
# drivers, so the toolchain never ships to production.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=dashboard_ui.settings \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
        libmariadb3 \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY dashboard_ui/ /app/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Bake the static files into the image so the container needs no writable
# volume at runtime. The dummy settings keep collectstatic from requiring a
# real SECRET_KEY or a reachable database during the build.
RUN DJANGO_SECRET_KEY=build-time-only \
    python manage.py collectstatic --noinput \
    && chown -R appuser:appuser /app/staticfiles

USER appuser

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]

# Railway sets $PORT; the shell form is what lets it be expanded at run time.
CMD ["sh", "-c", "exec gunicorn dashboard_ui.wsgi:application \
      --bind 0.0.0.0:${PORT:-8000} \
      --workers ${WEB_CONCURRENCY:-3} \
      --threads ${GUNICORN_THREADS:-2} \
      --timeout ${GUNICORN_TIMEOUT:-60} \
      --access-logfile - \
      --error-logfile -"]
