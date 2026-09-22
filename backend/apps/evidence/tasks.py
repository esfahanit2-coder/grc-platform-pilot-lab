from celery import shared_task
from django.conf import settings

from .malware import MalwareScannerError
from .malware_service import mark_scan_error, mark_scan_pending, scan_evidence_once
from .models import Evidence


@shared_task(bind=True, max_retries=5)
def scan_evidence_malware(self, evidence_id):
    try:
        evidence = scan_evidence_once(evidence_id)
    except Evidence.DoesNotExist:
        return {"status": "missing"}
    except MalwareScannerError as exc:
        retry_limit = int(getattr(settings, "EVIDENCE_MALWARE_SCAN_MAX_RETRIES", 3))
        retry_limit = max(0, min(retry_limit, 5))
        if getattr(exc, "retryable", False) and self.request.retries < retry_limit:
            mark_scan_pending(evidence_id, getattr(exc, "code", "scanner_unavailable"))
            delay = int(getattr(settings, "EVIDENCE_MALWARE_SCAN_RETRY_SECONDS", 30))
            raise self.retry(exc=exc, countdown=max(1, min(delay, 3600)))
        evidence = mark_scan_error(evidence_id, getattr(exc, "code", "scan_error"))

    metadata = evidence.metadata or {}
    return {
        "status": metadata.get("malware_scan_status", "error"),
        "error_code": metadata.get("malware_scan_error_code", ""),
        "attempts": metadata.get("malware_scan_attempts", 0),
    }
