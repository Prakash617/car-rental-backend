import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# Read .env file if present
env_file = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_file):
    environ.Env.read_env(env_file)

SECRET_KEY = env(
    "SECRET_KEY", default="django-insecure-dev-temporary-secret-key-change-in-production"
)
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", ".platform.com"])

# ==============================================================================
# DJANGO-TENANTS APPLICATION CONFIGURATION
# ==============================================================================

SHARED_APPS = [
    "django_tenants",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party shared
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    # Platform (Public Schema Only)
    "apps.platform.tenants",
    "apps.platform.domains",
    "apps.platform.subscriptions",
    "apps.platform.plans",
    "apps.platform.themes",
    "apps.platform.platform_users",
    "common",
]

TENANT_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    # Third party tenant apps
    "rest_framework",
    # Tenant Schemas (tenant_x)
    "apps.tenant.memberships",
    "apps.tenant.branches",
    "apps.tenant.vehicles",
    "apps.tenant.customers",
    "apps.tenant.bookings",
    "apps.tenant.pricing",
    "apps.tenant.payments",
    "apps.tenant.maintenance",
    "apps.tenant.notifications",
    "apps.tenant.websites",
    "apps.tenant.reports",
    "apps.tenant.audit",
]

INSTALLED_APPS = list(dict.fromkeys(SHARED_APPS + TENANT_APPS))

TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "domains.Domain"

PUBLIC_SCHEMA_URLCONF = "config.urls_public"
ROOT_URLCONF = "config.urls"

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

from corsheaders.defaults import default_headers

CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-forwarded-host",
    "x-tenant-host",
]

# ==============================================================================
# MIDDLEWARE
# ==============================================================================

MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.tenant_context.TenantContextMiddleware",
    "common.middleware.tenant_membership.TenantMembershipMiddleware",
]

# ==============================================================================
# DATABASE & ROUTERS
# ==============================================================================

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://car_rental_user:secure_dev_password@localhost:5432/car_rental",
    )
}
DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"

# ==============================================================================
# AUTHENTICATION
# ==============================================================================

AUTH_USER_MODEL = "platform_users.PlatformUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ==============================================================================
# REST FRAMEWORK & OPENAPI
# ==============================================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardLimitOffsetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "common.exceptions.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Car Rental SaaS API",
    "DESCRIPTION": "Production-grade Multi-Tenant Car Rental SaaS Platform API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ==============================================================================
# REDIS & CELERY
# ==============================================================================

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "car_rental_cache",
    }
}

# ==============================================================================
# INTERNATIONALIZATION & TIMEZONE
# ==============================================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ==============================================================================
# STATIC & MEDIA FILES
# ==============================================================================

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django_tenants": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ==============================================================================
# CELERY BEAT SCHEDULE
# ==============================================================================

CELERY_BEAT_SCHEDULE = {
    "check-overdue-rentals-hourly": {
        "task": "apps.tenant.bookings.tasks.check_overdue_rentals_all_tenants",
        "schedule": 3600.0,  # Every hour
    },
    "send-upcoming-pickup-reminders-15m": {
        "task": "apps.tenant.notifications.tasks.send_pickup_reminders_all_tenants",
        "schedule": 900.0,  # Every 15 minutes
    },
}
