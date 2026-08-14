# Deploying the dashboard to Railway

The deployable website is the Django project in `dashboard_ui/`. The computer
vision scripts at the repository root (`shavelog.py`, `multi_camera.py`,
`main.py`, …) are **not** part of the web service and are excluded from the
Docker image — they need a camera feed and a GPU-class runtime, neither of which
a Railway web service has.

## What is in the image

| File | Purpose |
| --- | --- |
| `Dockerfile` | Two-stage build: compiles the DB drivers in a builder stage, ships only the runtime libs (≈380 MB final image) |
| `docker-entrypoint.sh` | Waits for the database, runs `migrate`, then execs gunicorn |
| `railway.json` | Tells Railway to use the Dockerfile and health-check `/healthz` |
| `.dockerignore` | Keeps the CV scripts, the model weights, and local databases out of the build context |
| `docker-compose.yml` | Runs the same image locally against a MySQL container |

Static files are collected into `dashboard_ui/staticfiles/` at **build** time and
served by WhiteNoise, so no separate web server or volume is needed.

## Deploying

1. **Create the project.** In Railway: *New Project → Deploy from GitHub repo*
   and pick this repository. Railway detects `railway.json` and builds with the
   Dockerfile. Leave the service root directory as the repository root.

2. **Add the database.** *New → Database → MySQL* (Postgres works too — the
   settings accept either).

3. **Set the service variables.** On the web service, under *Variables*:

   ```
   DJANGO_SECRET_KEY   = <a long random string>
   DATABASE_URL        = ${{ MySQL.MYSQL_URL }}
   DJANGO_DEBUG        = false
   ```

   `DATABASE_URL` must use Railway's reference syntax (the `${{ ... }}` form) so
   it resolves to the private-network URL. For Postgres use
   `${{ Postgres.DATABASE_URL }}` instead.

   Generate the secret key with:

   ```bash
   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
   ```

4. **Generate a domain.** *Settings → Networking → Generate Domain*. Railway
   then injects `RAILWAY_PUBLIC_DOMAIN`, which the settings automatically add to
   both `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` — no extra configuration
   needed. For a **custom** domain, also set:

   ```
   DJANGO_ALLOWED_HOSTS        = shop.example.com
   DJANGO_CSRF_TRUSTED_ORIGINS = https://shop.example.com
   ```

5. **Create an admin user** — either once via the deploy shell:

   ```bash
   python manage.py createsuperuser
   ```

   or by setting `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL` and
   `DJANGO_SUPERUSER_PASSWORD`, which the entrypoint picks up on next boot.
   Remove those variables afterwards.

Migrations run automatically on every deploy. Set `RUN_MIGRATIONS=0` to skip
them.

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | insecure dev key | **Required in production** |
| `DJANGO_DEBUG` | `false` | Never enable on a public deploy |
| `DATABASE_URL` / `MYSQL_URL` | — | Full connection URL; falls back to `DB_*` vars, then sqlite |
| `DJANGO_ALLOWED_HOSTS` | localhost | Comma-separated; Railway's domain is added automatically |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | — | Comma-separated, **must include the scheme** |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` | Redirect http → https |
| `DJANGO_SECURE_COOKIES` | `true` | Set `false` only for local plain-HTTP runs |
| `DJANGO_SECURE_HSTS_SECONDS` | `0` | Opt-in; `31536000` once the domain is https-only for good |
| `PORT` | `8000` | Set by Railway |
| `WEB_CONCURRENCY` | `3` | Gunicorn workers |
| `RUN_MIGRATIONS` | `1` | Set `0` to skip migrations on boot |

## Running locally

```bash
cp .env.example .env          # then edit DJANGO_SECRET_KEY
docker compose up --build
```

The site is at http://localhost:8000. `docker-compose.yml` already overrides the
host/CSRF/cookie settings so plain HTTP works locally.

Without Compose:

```bash
docker build -t barbershop-web .
docker run -p 8000:8000 \
  -e DJANGO_SECRET_KEY=dev-key \
  -e DJANGO_SECURE_SSL_REDIRECT=false \
  -e DJANGO_SECURE_COOKIES=false \
  barbershop-web
```

With no `DATABASE_URL` set, the app falls back to sqlite, so this runs with no
database container at all.

## Notes

- **The CV features are inactive on Railway.** `views.py` imports `cv2` and
  `ultralytics` lazily inside the stream worker, so the site runs fine without
  them — a stream just reports status `error` instead of processing. Adding a
  camera stream is expected to fail in this environment: Railway containers
  cannot reach an on-premises RTSP camera, and the model weights plus torch
  would add ~2 GB to the image. Run the detection side on the barbershop's own
  machine and let it write to the same Railway database.
- **The health check is `/healthz`**, added in `dashboard_ui/urls.py`. It is
  exempt from the https redirect so Railway's internal probe succeeds.
