# Deploying the dashboard to Vercel

The deployable website is the Django project in `dashboard_ui/`. The computer
vision scripts at the repository root (`shavelog.py`, `multi_camera.py`,
`main.py`, …) are **not** part of the web service and are excluded from the
image — they need a camera feed and a GPU-class runtime, neither of which a
Vercel Function has.

Vercel [supports Dockerfiles](https://vercel.com/blog/dockerfile-on-vercel) as
of 30 June 2026: it detects a `Dockerfile.vercel` at the repository root,
builds the image, and runs it as a Vercel Function on Fluid compute. The only
hard contract is that **the server listens on `$PORT`** (Vercel routes to `80`
by default).

## What is in the repository

| File | Purpose |
| --- | --- |
| `Dockerfile.vercel` | The image Vercel builds. Two-stage, so the DB driver toolchain stays out of the final image (~380 MB) |
| `docker-entrypoint.sh` | Waits for the database and execs gunicorn. Skips migrations on Vercel — see below |
| `.dockerignore` | Keeps the CV scripts, model weights, and local databases out of the build context |
| `docker-compose.yml` | Runs the same image locally against a MySQL container |

Static files are collected into the image at **build** time and served by
WhiteNoise. Nothing is written at runtime, which matters because Vercel
containers are stateless with no durable storage.

## Deploying

1. **Import the project.** Vercel → *Add New → Project* → pick this repository.
   It detects `Dockerfile.vercel` and routes all traffic to the container.
   Leave the root directory as the repository root.

2. **Turn on system environment variables.** Project → Settings → Environment
   Variables → tick **"Enable access to System Environment Variables"**.

   This is not optional. `VERCEL_URL` and friends are what put your deployment
   hostname into `ALLOWED_HOSTS`. With it off, every request returns
   **400 DisallowedHost** unless you set `DJANGO_ALLOWED_HOSTS` by hand.

3. **Attach a database.** Vercel does not host MySQL, so the database lives
   elsewhere. Either is fine:
   - **Vercel Postgres / Neon** — add the integration and it sets `DATABASE_URL`.
   - **Keep an existing MySQL** — use its **public** connection URL. A private
     host such as `mysql.railway.internal` is unreachable from Vercel, and
     containers do not support Static IPs, so the database cannot be
     IP-allowlisted.

4. **Set the environment variables:**

   ```
   DJANGO_SECRET_KEY = <a long random string>
   DATABASE_URL      = <full connection URL>
   ```

   Generate the key with:

   ```bash
   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
   ```

5. **Run the migrations once, from your machine**, pointed at the same database:

   ```bash
   docker build -f Dockerfile.vercel -t barbershop .
   docker run --rm -e DJANGO_SECRET_KEY=migrate -e DATABASE_URL='<same URL>' \
     -e RUN_MIGRATIONS=1 barbershop python manage.py migrate
   ```

   Repeat this whenever a deploy adds a migration.

6. **Create an admin user** the same way:

   ```bash
   docker run --rm -it -e DJANGO_SECRET_KEY=admin -e DATABASE_URL='<same URL>' \
     barbershop python manage.py createsuperuser
   ```

### Why migrations do not run on deploy

On a long-running host, migrating at container start is convenient. On Vercel
it is not: containers autoscale and scale to zero after five minutes idle
(30 seconds on preview), so migrations would run on **every cold start** —
repeatedly, possibly concurrently, and adding latency to each one.

The entrypoint therefore defaults `RUN_MIGRATIONS` to `0` when `VERCEL` is set,
and `1` everywhere else. Set `RUN_MIGRATIONS=1` explicitly if you want the old
behaviour.

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | insecure dev key | **Required in production** |
| `DATABASE_URL` | — | Full connection URL; falls back to `DB_*` vars, then sqlite |
| `DJANGO_DEBUG` | `false` | Never enable on a public deploy |
| `DJANGO_ALLOWED_HOSTS` | localhost | Only needed if system env vars are off, or for a custom domain |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | — | Comma-separated, **must include the scheme** |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` | Redirect http → https |
| `DJANGO_SECURE_COOKIES` | `true` | Set `false` only for local plain-HTTP runs |
| `DJANGO_SECURE_HSTS_SECONDS` | `0` | Opt-in; `31536000` once the domain is https-only for good |
| `DB_CONN_MAX_AGE` | `0` on Vercel | Connections close per request; autoscaled containers would otherwise exhaust the DB connection limit |
| `RUN_MIGRATIONS` | `0` on Vercel | See above |
| `PORT` | `80` | Set by Vercel |
| `WEB_CONCURRENCY` | `2` | Gunicorn workers |

`VERCEL_URL`, `VERCEL_BRANCH_URL` and `VERCEL_PROJECT_PRODUCTION_URL` are read
automatically into `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`. Preview
deployments get a new hostname per push, so `https://*.vercel.app` is trusted
for CSRF as well.

## Running locally

```bash
cp .env.example .env          # then edit DJANGO_SECRET_KEY
docker compose up --build
```

The site is at http://localhost:8000. Compose overrides the host, CSRF and
cookie settings so plain HTTP works locally.

With no `DATABASE_URL` set the app falls back to sqlite, so a bare
`docker run` needs no database container at all.

## Notes

- **Custom domain:** add it in Vercel, then set `DJANGO_ALLOWED_HOSTS` and
  `DJANGO_CSRF_TRUSTED_ORIGINS` (with `https://`) to match.
- **The CV features are inactive here.** `views.py` imports `cv2` and
  `ultralytics` lazily inside the stream worker, so the site runs fine without
  them. Adding a camera stream cannot work on Vercel: containers are stateless
  and scale to zero, so a long-lived frame-processing thread has nowhere to
  live, they cannot reach an on-premises RTSP camera, and torch plus the model
  weights would add ~2 GB. Run detection on the barbershop's own machine and
  write to the same database.
- **`sync_shavelog` does not run in the container** — `.dockerignore` excludes
  `shavelog.db`, which is produced by the on-premises detector anyway.
- **`/healthz`** returns 200 for uptime checks and is exempt from the HTTPS
  redirect.
