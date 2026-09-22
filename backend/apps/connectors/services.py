import hashlib
import json
import os
import urllib.parse

from django.utils import timezone

from apps.audit.services import record_audit_event
from apps.evidence.models import Evidence

from .clients import connector_for, validate_secret_env_name
from .models import ConnectorRun


def _redacted_error(config, exc):
    text = str(exc)
    for env_name in (
        config.username_env_var,
        config.secret_env_var,
        config.secondary_secret_env_var,
    ):
        try:
            validate_secret_env_name(env_name)
        except Exception:
            continue
        if not env_name:
            continue
        value = os.getenv(env_name, "")
        if value:
            text = text.replace(value, "[REDACTED]")
    return text[:4000]


def _source_host(config):
    if config.connector_type == "active_directory":
        host = (config.configuration or {}).get("host") or config.base_url
        if isinstance(host, str) and "://" in host:
            return urllib.parse.urlparse(host).hostname or ""
        return str(host or "")
    return urllib.parse.urlparse(config.base_url or "").hostname or ""


def run_connector(config, *, user, request=None):
    run = ConnectorRun.objects.create(
        connector=config,
        triggered_by=user,
        status=ConnectorRun.Status.RUNNING,
    )
    try:
        result = connector_for(config).collect()
        collected_at = timezone.now()
        payload_text = json.dumps(
            result.payload,
            ensure_ascii=False,
            default=str,
            sort_keys=True,
            separators=(",", ":"),
        )
        payload_sha256 = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
        contract = result.payload if isinstance(result.payload, dict) else {}
        evidence = Evidence.objects.create(
            tenant=config.tenant,
            organization_unit=config.organization_unit,
            title=result.title,
            description=f"Automated evidence from connector {config.name}",
            evidence_type=Evidence.EvidenceType.CONFIGURATION,
            source=f"connector:{config.connector_type}:{config.id}",
            owner=user,
            collected_at=collected_at,
            classification=Evidence.Classification.INTERNAL,
            text_content=payload_text,
            metadata={
                "connector_id": str(config.id),
                "connector_run_id": str(run.id),
                "connector_type": config.connector_type,
                "source_host": _source_host(config),
                "collected_at": collected_at.isoformat(),
                "payload_sha256": payload_sha256,
                "provider_schema_version": contract.get("schema_version"),
                "provider": contract.get("provider") or config.connector_type,
                "dataset": contract.get("dataset"),
                "summary": contract.get("summary") if isinstance(contract.get("summary"), dict) else {},
                "automated": True,
                "collection_mode": "read_only",
                "human_review_required": True,
                "asserts_compliance": False,
            },
        )
        run.status = ConnectorRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.summary = {
            "evidence_id": str(evidence.id),
            "title": result.title,
            "payload_sha256": payload_sha256,
            "provider_schema_version": contract.get("schema_version"),
            "dataset": contract.get("dataset"),
            "fact_summary": contract.get("summary") if isinstance(contract.get("summary"), dict) else {},
        }
        run.save(update_fields=["status", "finished_at", "summary", "updated_at"])
        config.last_sync_at = run.finished_at
        config.last_status = "succeeded"
        config.last_error = ""
        config.save(update_fields=["last_sync_at", "last_status", "last_error", "updated_at"])
        record_audit_event(
            user,
            config.tenant,
            "connector.run",
            "connector_config",
            config.id,
            metadata={
                "connector_type": config.connector_type,
                "connector_run_id": str(run.id),
                "evidence_id": str(evidence.id),
                "payload_sha256": payload_sha256,
                "provider_schema_version": contract.get("schema_version"),
                "dataset": contract.get("dataset"),
            },
            request=request,
        )
        return run, evidence
    except Exception as exc:
        safe_error = _redacted_error(config, exc)
        run.status = ConnectorRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error = safe_error
        run.save(update_fields=["status", "finished_at", "error", "updated_at"])
        config.last_sync_at = run.finished_at
        config.last_status = "failed"
        config.last_error = safe_error
        config.save(update_fields=["last_sync_at", "last_status", "last_error", "updated_at"])
        record_audit_event(
            user,
            config.tenant,
            "connector.run",
            "connector_config",
            config.id,
            outcome="failure",
            metadata={
                "connector_type": config.connector_type,
                "connector_run_id": str(run.id),
                "error": safe_error,
            },
            request=request,
        )
        raise
