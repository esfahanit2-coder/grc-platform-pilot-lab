from pathlib import Path
from datetime import timedelta
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [x.strip() for x in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if x.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "apps.common",
    "apps.tenancy",
    "apps.identity",
    "apps.organizations",
    "apps.audit",
    "apps.frameworks",
    "apps.controls",
    "apps.assets",
    "apps.actions",
    "apps.risks",
    "apps.assessments",
    "apps.evidence",
    "apps.findings",
    "apps.internal_audits",
    "apps.documents",
    "apps.reporting",
    "apps.ai_gateway",
    "apps.workflows",
    "apps.notifications",
    "apps.connectors",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.audit.middleware.CorrelationIdMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.tenancy.middleware.TenantHeaderMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "grc"),
        "USER": os.getenv("POSTGRES_USER", "grc"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "grc"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

if os.getenv("DJANGO_USE_SQLITE", "0") == "1":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "runtime-validation.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("apps.identity.authentication.CookieOrHeaderJWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": os.getenv("AUTH_LOGIN_RATE", "10/min"),
        "auth_mfa": os.getenv("AUTH_MFA_RATE", "12/min"),
        "auth_refresh": os.getenv("AUTH_REFRESH_RATE", "30/min"),
    },
    # `format` is reserved by our export endpoints (for example RTP DOCX).
    # Disable DRF's query-parameter renderer override to avoid intercepting it.
    "URL_FORMAT_OVERRIDE": None,
}
SPECTACULAR_SETTINGS = {
    "TITLE": "GRC Platform API",
    "DESCRIPTION": "Sprint 6 API — AI Gateway, RAG, workflow, notifications and production hardening",
    "VERSION": "0.8.0-pilot",
}

CORS_ALLOWED_ORIGINS = [x.strip() for x in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if x.strip()]

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/1"))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_TASK_TRACK_STARTED = True

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "grc-evidence")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_USE_SSL = os.getenv("S3_USE_SSL", "0") == "1"

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

MFA_ENCRYPTION_KEY = os.getenv("MFA_ENCRYPTION_KEY", "")
MFA_ISSUER = os.getenv("MFA_ISSUER", "GRC Platform")

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=8),
    "ROTATE_REFRESH_TOKENS": False,
}

EVIDENCE_MAX_FILE_SIZE = int(os.getenv("EVIDENCE_MAX_FILE_SIZE", str(25 * 1024 * 1024)))

# Sprint 6 — production/security defaults
APP_ENV = os.getenv("APP_ENV", "development")
OPS_ASYNC_HEARTBEAT_MAX_AGE_SECONDS = int(os.getenv("OPS_ASYNC_HEARTBEAT_MAX_AGE_SECONDS", "180"))
OPS_BACKUP_MAX_AGE_HOURS = int(os.getenv("OPS_BACKUP_MAX_AGE_HOURS", "26"))
OPS_CELERY_QUEUE_WARN_DEPTH = int(os.getenv("OPS_CELERY_QUEUE_WARN_DEPTH", "1000"))
OPS_METRICS_TOKEN = os.getenv("OPS_METRICS_TOKEN", "").strip()
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "1" if APP_ENV == "production" else "0") == "1"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "1" if APP_ENV == "production" else "0") == "1"
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "0") == "1"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if APP_ENV == "production" else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "0") == "1"
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()]
AI_ENABLED = os.getenv("AI_ENABLED", "1") == "1"
AI_DEFAULT_CLASSIFICATION = os.getenv("AI_DEFAULT_CLASSIFICATION", "internal")
AI_MAX_CONTEXT_CHARS = int(os.getenv("AI_MAX_CONTEXT_CHARS", "24000"))
AI_RAG_MODE = os.getenv("AI_RAG_MODE", "hybrid")  # lexical | semantic | hybrid
AI_EMBED_BATCH_SIZE = int(os.getenv("AI_EMBED_BATCH_SIZE", "32"))
CONNECTOR_HTTP_TIMEOUT = int(os.getenv("CONNECTOR_HTTP_TIMEOUT", "30"))
CONNECTOR_MAX_RESPONSE_BYTES = int(os.getenv("CONNECTOR_MAX_RESPONSE_BYTES", str(5 * 1024 * 1024)))
EVIDENCE_REQUIRE_CLEAN_DOWNLOAD = os.getenv(
    "EVIDENCE_REQUIRE_CLEAN_DOWNLOAD",
    "1" if APP_ENV == "production" else "0",
) == "1"

# Evidence malware scanning is deliberately disabled until an approved scanner
# endpoint exists. Production download remains fail-closed while status is not
# clean. clamd TCP provides no authentication or encryption; use only a trusted
# private/protected network path or an equivalent approved transport boundary.
EVIDENCE_MALWARE_SCANNER = os.getenv("EVIDENCE_MALWARE_SCANNER", "disabled").strip().lower()
EVIDENCE_MALWARE_SCAN_AUTOSUBMIT = os.getenv("EVIDENCE_MALWARE_SCAN_AUTOSUBMIT", "1") == "1"
EVIDENCE_MALWARE_SCAN_MAX_RETRIES = int(os.getenv("EVIDENCE_MALWARE_SCAN_MAX_RETRIES", "3"))
EVIDENCE_MALWARE_SCAN_RETRY_SECONDS = int(os.getenv("EVIDENCE_MALWARE_SCAN_RETRY_SECONDS", "30"))
CLAMD_HOST = os.getenv("CLAMD_HOST", "").strip()
CLAMD_PORT = int(os.getenv("CLAMD_PORT", "3310"))
CLAMD_TIMEOUT_SECONDS = float(os.getenv("CLAMD_TIMEOUT_SECONDS", "15"))
CLAMD_CHUNK_SIZE = int(os.getenv("CLAMD_CHUNK_SIZE", str(1024 * 1024)))

# Security throttles must be shared across production workers. Django's native
# Redis cache backend keeps login/MFA counters process-independent; tests and
# development remain self-contained with LocMemCache.
if APP_ENV == "production":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("AUTH_THROTTLE_REDIS_URL", os.getenv("REDIS_URL", "redis://redis:6379/0")),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "grc-security-throttles",
        }
    }

CELERY_BEAT_SCHEDULE = {
    "overdue-action-notifications-hourly": {
        "task": "apps.notifications.tasks.create_overdue_action_notifications",
        "schedule": 3600.0,
    },
    "operational-heartbeat-every-minute": {
        "task": "apps.common.tasks.record_async_heartbeat",
        "schedule": 60.0,
    },
}

AUTH_COOKIE_MODE = os.getenv("AUTH_COOKIE_MODE", "1" if APP_ENV == "production" else "0") == "1"
AUTH_ACCESS_COOKIE = os.getenv("AUTH_ACCESS_COOKIE", "grc_access")
AUTH_REFRESH_COOKIE = os.getenv("AUTH_REFRESH_COOKIE", "grc_refresh")
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "Strict")
CSRF_COOKIE_SAMESITE = AUTH_COOKIE_SAMESITE
CORS_ALLOW_CREDENTIALS = AUTH_COOKIE_MODE


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "apps.common.logging.SafeJsonFormatter"},
    },
    "handlers": {
        "console_json": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "loggers": {
        "grc": {
            "handlers": ["console_json"],
            "level": os.getenv("GRC_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console_json"],
            "level": os.getenv("DJANGO_REQUEST_LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
    },
}


# Notification email delivery — credentials are environment-only.
NOTIFICATION_EMAIL_ENABLED = os.getenv("NOTIFICATION_EMAIL_ENABLED", "0") == "1"
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
    if NOTIFICATION_EMAIL_ENABLED
    else "django.core.mail.backends.locmem.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "0") == "1"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "15"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "grc@localhost")
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[GRC]")
APP_BASE_URL = os.getenv("APP_BASE_URL", "").strip()
NOTIFICATION_EMAIL_MAX_ATTEMPTS = int(os.getenv("NOTIFICATION_EMAIL_MAX_ATTEMPTS", "5"))
NOTIFICATION_EMAIL_RETRY_SECONDS = int(os.getenv("NOTIFICATION_EMAIL_RETRY_SECONDS", "300"))
NOTIFICATION_DUE_SOON_DAYS = int(os.getenv("NOTIFICATION_DUE_SOON_DAYS", "3"))

CELERY_BEAT_SCHEDULE.update(
    {
        "due-action-notifications-hourly": {
            "task": "apps.notifications.tasks.create_due_action_notifications",
            "schedule": 3600.0,
        },
        "retry-failed-email-deliveries-every-five-minutes": {
            "task": "apps.notifications.tasks.retry_failed_email_deliveries",
            "schedule": 300.0,
        },
        "operational-alert-notifications-every-fifteen-minutes": {
            "task": "apps.notifications.tasks.create_operational_alert_notifications",
            "schedule": 900.0,
        },
    }
)
