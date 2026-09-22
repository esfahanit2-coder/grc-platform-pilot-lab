import json
import logging
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.identity.models import UserRoleScope
from apps.identity.services import bootstrap_tenant_rbac
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership

from .logging import SafeJsonFormatter
from .models import OperationalSignal
from .tasks import record_async_heartbeat


class OperationalStatusTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="ops-admin", password="StrongPassword123!"
        )
        self.scoped = User.objects.create_user(
            username="ops-scoped", password="StrongPassword123!"
        )
        self.tenant = Tenant.objects.create(name="Ops Tenant", code="ops-tenant")
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.admin, role_code="admin"
        )
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.scoped, role_code="member"
        )
        roles = bootstrap_tenant_rbac(self.tenant, admin_user=self.admin)
        self.unit = OrganizationUnit.objects.create(
            tenant=self.tenant,
            unit_type=OrganizationUnit.UnitType.COMPANY,
            code="HQ",
            name="Head Office",
        )
        UserRoleScope.objects.create(
            user=self.scoped,
            tenant=self.tenant,
            role=roles["tenant_admin"],
            organization_unit=self.unit,
        )

    def auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def seed_fresh_signals(self):
        OperationalSignal.objects.update_or_create(
            key="async-heartbeat",
            defaults={
                "status": OperationalSignal.Status.OK,
                "source": "test",
                "observed_at": timezone.now(),
                "metadata": {"task": "heartbeat"},
            },
        )
        OperationalSignal.objects.update_or_create(
            key="backup",
            defaults={
                "status": OperationalSignal.Status.OK,
                "source": "test",
                "observed_at": timezone.now(),
                "metadata": {"backup_name": "backup-1", "outcome": "success"},
            },
        )

    def mocked_dependencies(self, queue_depth=0):
        return (
            patch(
                "apps.common.operations.probe_database",
                return_value={"database_version": "PostgreSQL", "pgvector_version": None},
            ),
            patch(
                "apps.common.operations.probe_redis",
                return_value={"queue_name": "celery", "queue_depth": queue_depth},
            ),
            patch(
                "apps.common.operations.probe_objectstore",
                return_value={"reachable": True},
            ),
        )

    def test_whole_tenant_security_view_can_read_healthy_status(self):
        self.auth(self.admin)
        self.seed_fresh_signals()
        db, redis_probe, storage = self.mocked_dependencies()
        with db, redis_probe, storage:
            response = self.client.get("/api/v1/operations/status/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["overall_status"], "healthy")
        self.assertEqual(body["components"]["async_pipeline"]["status"], "ok")
        self.assertEqual(body["components"]["backup"]["status"], "ok")
        self.assertEqual(body["components"]["queue"]["details"]["depth"], 0)

    def test_scoped_security_permission_cannot_read_deployment_status(self):
        self.auth(self.scoped)
        response = self.client.get("/api/v1/operations/status/")
        self.assertEqual(response.status_code, 403)

    @override_settings(
        APP_ENV="production",
        OPS_ASYNC_HEARTBEAT_MAX_AGE_SECONDS=60,
        OPS_BACKUP_MAX_AGE_HOURS=1,
    )
    def test_stale_heartbeat_and_backup_are_critical_in_production(self):
        self.auth(self.admin)
        stale = timezone.now() - timedelta(hours=2)
        OperationalSignal.objects.create(
            key="async-heartbeat",
            status=OperationalSignal.Status.OK,
            source="test",
            observed_at=stale,
        )
        OperationalSignal.objects.create(
            key="backup",
            status=OperationalSignal.Status.OK,
            source="test",
            observed_at=stale,
        )
        db, redis_probe, storage = self.mocked_dependencies()
        with db, redis_probe, storage:
            response = self.client.get("/api/v1/operations/status/")
        body = response.json()
        self.assertEqual(body["overall_status"], "critical")
        self.assertEqual(body["components"]["async_pipeline"]["status"], "critical")
        self.assertEqual(body["components"]["async_pipeline"]["details"]["reason"], "stale")
        self.assertEqual(body["components"]["backup"]["status"], "critical")

    def test_failed_backup_signal_is_critical(self):
        self.auth(self.admin)
        OperationalSignal.objects.create(
            key="async-heartbeat",
            status=OperationalSignal.Status.OK,
            source="test",
            observed_at=timezone.now(),
        )
        OperationalSignal.objects.create(
            key="backup",
            status=OperationalSignal.Status.CRITICAL,
            source="pilot-backup",
            observed_at=timezone.now(),
            metadata={"backup_name": "broken", "outcome": "failed"},
        )
        db, redis_probe, storage = self.mocked_dependencies()
        with db, redis_probe, storage:
            response = self.client.get("/api/v1/operations/status/")
        self.assertEqual(response.json()["components"]["backup"]["status"], "critical")
        self.assertEqual(response.json()["overall_status"], "critical")

    @override_settings(OPS_CELERY_QUEUE_WARN_DEPTH=5)
    def test_queue_depth_threshold_produces_warning(self):
        self.auth(self.admin)
        self.seed_fresh_signals()
        db, redis_probe, storage = self.mocked_dependencies(queue_depth=6)
        with db, redis_probe, storage:
            response = self.client.get("/api/v1/operations/status/")
        body = response.json()
        self.assertEqual(body["components"]["queue"]["status"], "warning")
        self.assertEqual(body["overall_status"], "degraded")

    def test_dependency_exception_does_not_leak_secret_text(self):
        self.auth(self.admin)
        self.seed_fresh_signals()
        with (
            patch(
                "apps.common.operations.probe_database",
                return_value={"database_version": "PostgreSQL", "pgvector_version": None},
            ),
            patch(
                "apps.common.operations.probe_redis",
                side_effect=RuntimeError("redis://user:super-secret@private-host:6379/1"),
            ),
            patch(
                "apps.common.operations.probe_objectstore",
                return_value={"reachable": True},
            ),
        ):
            response = self.client.get("/api/v1/operations/status/")
        body_text = json.dumps(response.json())
        self.assertNotIn("super-secret", body_text)
        self.assertNotIn("private-host", body_text)
        self.assertEqual(
            response.json()["components"]["redis"]["details"]["error_type"],
            "RuntimeError",
        )

    def test_public_health_endpoints_remain_minimal(self):
        self.client.credentials()
        live = self.client.get("/api/v1/health/live")
        ready = self.client.get("/api/v1/health/ready")
        self.assertEqual(live.status_code, 200)
        self.assertEqual(ready.status_code, 200)
        self.assertNotIn("components", live.json())
        self.assertNotIn("components", ready.json())
        self.assertNotIn("redis", ready.json())

    def test_heartbeat_task_records_round_trip_signal(self):
        record_async_heartbeat()
        signal = OperationalSignal.objects.get(key="async-heartbeat")
        self.assertEqual(signal.status, OperationalSignal.Status.OK)
        self.assertEqual(signal.source, "celery-beat-worker")


class DatacenterObservabilityTests(OperationalStatusTests):
    @override_settings(APP_ENV="production", OPS_METRICS_TOKEN="")
    def test_production_metrics_fail_closed_when_token_is_unconfigured(self):
        self.client.credentials()
        response = self.client.get("/api/v1/operations/metrics/")
        self.assertEqual(response.status_code, 503)

    @override_settings(APP_ENV="production", OPS_METRICS_TOKEN="metrics-test-token")
    def test_metrics_require_bearer_token_and_do_not_expose_customer_labels(self):
        self.seed_fresh_signals()
        db, redis_probe, storage = self.mocked_dependencies(queue_depth=7)

        self.client.credentials()
        with db, redis_probe, storage:
            denied = self.client.get("/api/v1/operations/metrics/")
        self.assertEqual(denied.status_code, 403)

        db, redis_probe, storage = self.mocked_dependencies(queue_depth=7)
        with db, redis_probe, storage:
            response = self.client.get(
                "/api/v1/operations/metrics/",
                HTTP_AUTHORIZATION="Bearer metrics-test-token",
            )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("grc_operational_health", body)
        self.assertIn('grc_component_health{component="database"}', body)
        self.assertIn("grc_celery_queue_depth 7", body)
        self.assertNotIn(self.tenant.code, body)
        self.assertNotIn(self.admin.username, body)
        self.assertNotIn("backup-1", body)
        self.assertNotIn("X-Tenant", body)

    def test_json_log_formatter_redacts_credentials_and_emits_only_safe_context(self):
        formatter = SafeJsonFormatter()
        record = logging.LogRecord(
            name="grc.request",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=(
                "request token=super-secret "
                "https://user:password@private-host.example/internal"
            ),
            args=(),
            exc_info=None,
        )
        record.request_id = "11111111-1111-1111-1111-111111111111"
        record.method = "GET"
        record.path = "/api/v1/health/live"
        record.status_code = 200
        record.duration_ms = 12.5
        record.customer_payload = "DO_NOT_LOG_THIS_CUSTOMER_VALUE"

        payload = json.loads(formatter.format(record))
        rendered = json.dumps(payload)
        self.assertEqual(payload["message"].count("[REDACTED]"), 2)
        self.assertNotIn("super-secret", rendered)
        self.assertNotIn("user:password", rendered)
        self.assertNotIn("private-host.example", rendered)
        self.assertNotIn("DO_NOT_LOG_THIS_CUSTOMER_VALUE", rendered)
        self.assertEqual(payload["request_id"], record.request_id)
        self.assertEqual(payload["status_code"], "200")
