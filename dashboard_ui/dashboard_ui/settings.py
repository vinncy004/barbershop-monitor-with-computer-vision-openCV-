import os
from pathlib import Path

import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name):
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


# Railway injects these automatically for the service.
RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
RAILWAY_PRIVATE_DOMAIN = os.environ.get("RAILWAY_PRIVATE_DOMAIN", "")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-local-development-key-only")
DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS") or ["localhost", "127.0.0.1", "[::1]"]
# Railway's health check probe arrives with Host: healthcheck.railway.app, not
# the public domain. Without it here Django answers 400 DisallowedHost, the
# check never goes green, and the deploy is rolled back.
for domain in (RAILWAY_PUBLIC_DOMAIN, RAILWAY_PRIVATE_DOMAIN, "healthcheck.railway.app"):
    if domain and domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(domain)
if env_bool("DJANGO_ALLOW_ALL_HOSTS"):
    ALLOWED_HOSTS = ["*"]

# Django 4+ checks the Origin header on unsafe requests, and behind Railway's proxy
# the request looks like https://<domain>, so that origin has to be trusted explicitly.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if RAILWAY_PUBLIC_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))

# Railway terminates TLS at its edge and forwards plain HTTP to the container.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    # Set DJANGO_SECURE_COOKIES=false only when serving over plain HTTP (local
    # container runs); over https the cookies must stay Secure.
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    # Railway's health check probes the container over plain HTTP, so that one
    # path must not be redirected to https.
    SECURE_REDIRECT_EXEMPT = [r"^healthz/?$"]
    # Opt-in: HSTS is hard to undo once a browser has cached it, so enable it
    # (e.g. 31536000) only once the domain is settled on https for good.
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))

INSTALLED_APPS = [
    "dashboard_app",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "dashboard_ui.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "dashboard_app" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "dashboard_ui.wsgi.application"

# Railway exposes the database as a single connection URL (DATABASE_URL for
# Postgres, MYSQL_URL for the MySQL plugin). Fall back to the discrete DB_*
# variables, and finally to sqlite so the project still runs locally with no
# configuration at all.
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_URL")
CONN_MAX_AGE = int(os.environ.get("DB_CONN_MAX_AGE", "600"))

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=CONN_MAX_AGE,
            conn_health_checks=True,
        )
    }
elif os.environ.get("DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.mysql"),
            "NAME": os.environ.get("DB_NAME", "railway"),
            "USER": os.environ.get("DB_USER", "root"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ["DB_HOST"],
            "PORT": os.environ.get("DB_PORT", "3306"),
            "CONN_MAX_AGE": CONN_MAX_AGE,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# dashboard_app/static/ is already picked up by AppDirectoriesFinder; listing it
# here as well made collectstatic report every file as a duplicate.

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "dashboard_app.User"
LOGIN_URL = "dashboard_app:login"
LOGIN_REDIRECT_URL = "dashboard_app:dashboard"
LOGOUT_REDIRECT_URL = "dashboard_app:login"
