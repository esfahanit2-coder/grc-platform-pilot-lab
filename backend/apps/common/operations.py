import os
from datetime import timedelta

import redis
from django.conf import settings
from django.db import connection
from django.utils import timezone

from apps.common.storage import S3ObjectStorage

from .models import OperationalSignal


STATUS_RANK = {"ok": 0, "unknown": 1, "warning": 2, "critical": 3}


def probe_database(require_pgvector=False):
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        database_version = cursor.fetchone()[0]
        pgvector_version = None
        if require_pgvector:
            cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("pgvector extension is not enabled")
            pgvector_version = row[0]
    return {"database_version": database_version, "pgvector_version": pgvector_version}


def _redis_url():
    return os.getenv("REDIS_URL", getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0"))


def probe_redis():
    url = _redis_url()
    client = redis.Redis.from_url(url, socket_timeout=3, socket_connect_timeout=3)
    client.ping()
    queue_name = getattr(settings, "CELERY_DEFAULT_QUEUE", "celery")
    queue_depth = None
    broker_url = str(getattr(settings, "CELERY_BROKER_URL", ""))
    if broker_url.startswith(("redis://", "rediss://")):
        broker = redis.Redis.from_url(broker_url, socket_timeout=3, socket_connect_timeout=3)
        queue_depth = int(broker.llen(queue_name))
    return {"queue_name": queue_name, "queue_depth": queue_depth}


def probe_objectstore():
    storage = S3ObjectStorage()
    storage._client().head_bucket(Bucket=storage.bucket)
    return {"reachable": True}


def record_operational_signal(key, status, source, metadata=None, observed_at=None):
    if status not in OperationalSignal.Status.values:
        raise ValueError("Unsupported operational signal status.")
    signal, _ = OperationalSignal.objects.update_or_create(
        key=key,
        defaults={
            "status": status,
            "source": source,
            "observed_at": observed_at or timezone.now(),
            "metadata": dict(metadata or {}),
            "deleted_at": None,
        },
    )
    return signal


def _live_component(probe, *, label):
    try:
        details = probe()
        return {"label": label, "status": "ok", "details": details}
    except Exception as exc:
        return {
            "label": label,
            "status": "critical",
            "details": {"error_type": type(exc).__name__},
        }


def _signal_component(key, *, label, max_age_seconds, production_required=False):
    signal = OperationalSignal.objects.filter(key=key, deleted_at__isnull=True).first()
    if not signal:
        return {
            "label": label,
            "status": "critical" if production_required else "warning",
            "observed_at": None,
            "age_seconds": None,
            "details": {"reason": "not_recorded"},
        }

    now = timezone.now()
    age = max(0, int((now - signal.observed_at).total_seconds()))
    status = signal.status
    reason = None
    if status != OperationalSignal.Status.CRITICAL and age > max_age_seconds:
        status = "critical" if production_required else "warning"
        reason = "stale"

    safe_metadata = {
        key: value
        for key, value in (signal.metadata or {}).items()
        if key in {
            "backup_name",
            "duration_seconds",
            "release_consistent_quiesce",
            "outcome",
            "task",
        }
    }
    details = {"source": signal.source, **safe_metadata}
    if reason:
        details["reason"] = reason
    return {
        "label": label,
        "status": status,
        "observed_at": signal.observed_at,
        "age_seconds": age,
        "details": details,
    }


def _database_status_probe():
    probe_database(require_pgvector=False)
    return {"reachable": True}


def build_operational_status():
    production = getattr(settings, "APP_ENV", "development") == "production"
    components = {
        "database": _live_component(_database_status_probe, label="Database"),
        "redis": _live_component(probe_redis, label="Redis / broker"),
        "object_storage": _live_component(probe_objectstore, label="Object storage"),
    }

    redis_details = components["redis"].get("details") or {}
    queue_depth = redis_details.get("queue_depth")
    if components["redis"]["status"] == "critical":
        components["queue"] = {
            "label": "Celery queue",
            "status": "critical",
            "details": {"reason": "broker_unreachable"},
        }
    elif queue_depth is None:
        components["queue"] = {
            "label": "Celery queue",
            "status": "unknown",
            "details": {"reason": "queue_depth_not_available"},
        }
    else:
        warn_depth = int(getattr(settings, "OPS_CELERY_QUEUE_WARN_DEPTH", 1000))
        components["queue"] = {
            "label": "Celery queue",
            "status": "warning" if queue_depth > warn_depth else "ok",
            "details": {"depth": queue_depth, "warning_threshold": warn_depth},
        }

    components["async_pipeline"] = _signal_component(
        "async-heartbeat",
        label="Beat → broker → worker heartbeat",
        max_age_seconds=int(getattr(settings, "OPS_ASYNC_HEARTBEAT_MAX_AGE_SECONDS", 180)),
        production_required=production,
    )
    components["backup"] = _signal_component(
        "backup",
        label="Latest backup",
        max_age_seconds=int(getattr(settings, "OPS_BACKUP_MAX_AGE_HOURS", 26)) * 3600,
        production_required=production,
    )

    worst = max(STATUS_RANK[item["status"]] for item in components.values())
    if worst >= STATUS_RANK["critical"]:
        overall = "critical"
    elif worst >= STATUS_RANK["warning"]:
        overall = "degraded"
    elif worst >= STATUS_RANK["unknown"]:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "schema_version": 1,
        "overall_status": overall,
        "observed_at": timezone.now(),
        "environment": getattr(settings, "APP_ENV", "development"),
        "components": components,
    }
