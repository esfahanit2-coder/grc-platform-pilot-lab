from celery import shared_task

from .operations import record_operational_signal


@shared_task(name="apps.common.tasks.record_async_heartbeat")
def record_async_heartbeat():
    signal = record_operational_signal(
        "async-heartbeat",
        "ok",
        "celery-beat-worker",
        metadata={"task": "apps.common.tasks.record_async_heartbeat"},
    )
    return {"observed_at": signal.observed_at.isoformat(), "status": signal.status}
