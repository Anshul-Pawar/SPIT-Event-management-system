"""
SPIT Event Management: Django settings.

The database schema (22 tables, views, triggers) is created from sql/*.sql, NOT by Django.
Django only manages: app_user, DRF tokens, and its own django_* bookkeeping tables.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "rest_framework.authtoken",
    # project apps
    "common",
    "accounts",
    "directory",
    "committees",
    "events",
    "venues",
    "registrations",
    "monitoring",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "spit_events"),
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        # Each request is NOT wrapped automatically: views use transaction.atomic() explicitly,
        # so trigger errors surface cleanly to common.exceptions.api_exception_handler.
        "ATOMIC_REQUESTS": False,
    }
}

AUTH_USER_MODEL = "accounts.AppUser"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    # Reads that are public say so explicitly with AllowAny. Everything else needs a token.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
}

# --- App-specific settings -------------------------------------------------
# Only addresses on this domain can sign up or log in.
ALLOWED_EMAIL_DOMAIN = "spit.ac.in"
# The one root admin: permanent, and the only account that can make other admins permanent.
# Create it with:  python manage.py create_app_user --email <this>
ROOT_ADMIN_EMAIL = os.environ.get("ROOT_ADMIN_EMAIL", "anshul.pawar25@spit.ac.in")

# Payment: no gateway yet. Swap this dotted path when a real one exists.
PAYMENT_GATEWAY = "registrations.payments.RecordOnlyGateway"

# Folder with the HTML/CSS/JS front end (served by config/urls.py).
WEB_DIR = BASE_DIR / "web"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = False
# DATETIME columns in the schema are naive; keep Django naive too.
USE_TZ = False

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"spit": {"handlers": ["console"], "level": "INFO"}},
}
