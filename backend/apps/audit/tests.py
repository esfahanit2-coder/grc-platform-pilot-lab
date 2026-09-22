import io
import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.identity.services import bootstrap_tenant_rbac
from apps.tenancy.models import Tenant, TenantMembership

from .integrity import AuditIntegrityConfigurationError, integrity_key_bytes, scope_key_for_tenant_id
from .models import AuditChainState, AuditEvent, AuditIntegrityMutationError
from .services import record_audit_event
from .verification import verify_audit_scope


class AuditTrailTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="auditor-admin", password="StrongPassword123!")
        self.tenant = Tenant.objects.create(name="Audit Tenant", code="audit-tenant")
        TenantMembership.objects.create(tenant=self.tenant, user=self.user, role_code="admin")
        bootstrap_tenant_rbac(self.tenant, admin_user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.user).access_token}", HTTP_X_TENANT_ID=str(self.tenant.id))

    def test_audit_event_api_returns_before_after_and_integrity_metadata(self):
        event = record_audit_event(
            self.user,
            self.tenant,
            "tenant.update",
            "tenant",
            self.tenant.id,
            old_data={"name": "A"},
            new_data={"name": "B"},
        )
        response = self.client.get("/api/v1/audit-events/")
        self.assertEqual(response.status_code, 200)
        payload = response.data["results"][0]
        self.assertEqual(payload["old_data"]["name"], "A")
        self.assertEqual(payload["new_data"]["name"], "B")
        self.assertEqual(payload["chain_sequence"], 1)
        self.assertEqual(payload["previous_hash"], event.previous_hash)
        self.assertEqual(payload["event_hash"], event.event_hash)
        self.assertEqual(payload["integrity_key_id"], event.integrity_key_id)

    def test_audit_event_contains_integrity_fields(self):
        event = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        self.assertTrue(event.event_hash)
        self.assertTrue(event.integrity_key_id)
        self.assertEqual(event.chain_sequence, 1)

    def test_audit_chain_links_events(self):
        first = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        second = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        self.assertEqual(second.chain_sequence, 2)
        self.assertEqual(second.previous_hash, first.event_hash)

    def test_audit_event_update_is_forbidden(self):
        event = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        event.object_repr = "tampered"
        with self.assertRaises(AuditIntegrityMutationError):
            event.save()

    def test_audit_event_delete_is_forbidden(self):
        event = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        with self.assertRaises(AuditIntegrityMutationError):
            event.delete()

    def test_audit_chain_isolated_between_tenants(self):
        tenant_b = Tenant.objects.create(name="Audit Tenant B", code="audit-tenant-b")
        TenantMembership.objects.create(tenant=tenant_b, user=self.user, role_code="admin")
        bootstrap_tenant_rbac(tenant_b, admin_user=self.user)

        first_a = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        second_a = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        first_b = record_audit_event(self.user, tenant_b, "tenant.update", "tenant", tenant_b.id)

        self.assertEqual(first_a.chain_sequence, 1)
        self.assertEqual(second_a.chain_sequence, 2)
        self.assertEqual(first_b.chain_sequence, 1)
        self.assertNotEqual(second_a.event_hash, first_b.event_hash)

    def test_verifier_accepts_valid_chain(self):
        record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)

        result = verify_audit_scope(self.tenant.id)

        self.assertTrue(result.ok, result.as_dict())
        self.assertEqual(result.event_count, 2)

    def test_verifier_detects_database_field_tampering(self):
        event = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        AuditEvent.system_objects.filter(pk=event.pk).update(object_repr="database-tamper")

        result = verify_audit_scope(self.tenant.id)
        codes = {finding.code for finding in result.findings}

        self.assertFalse(result.ok)
        self.assertIn("event_hash_mismatch", codes)

    def test_verifier_detects_deleted_event_gap(self):
        first = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        table = connection.ops.quote_name(AuditEvent._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table} WHERE id = %s", [first.id])

        result = verify_audit_scope(self.tenant.id)
        codes = {finding.code for finding in result.findings}

        self.assertFalse(result.ok)
        self.assertIn("sequence_mismatch", codes)
        self.assertIn("previous_hash_mismatch", codes)

    def test_verifier_detects_chain_head_mismatch(self):
        record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        scope_key = scope_key_for_tenant_id(self.tenant.id)
        AuditChainState.objects.filter(scope_key=scope_key).update(last_hash="f" * 64)

        result = verify_audit_scope(self.tenant.id)
        codes = {finding.code for finding in result.findings}

        self.assertFalse(result.ok)
        self.assertIn("chain_head_hash_mismatch", codes)

    def test_actor_set_null_does_not_invalidate_integrity(self):
        event = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        actor_username = event.actor_username

        self.user.delete()
        event = AuditEvent.system_objects.get(pk=event.pk)

        self.assertIsNone(event.actor_id)
        self.assertEqual(event.actor_username, actor_username)
        result = verify_audit_scope(self.tenant.id)
        self.assertTrue(result.ok, result.as_dict())

    def test_verification_command_emits_machine_readable_json(self):
        record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        stdout = io.StringIO()

        call_command(
            "verify_audit_integrity",
            "--tenant-id",
            str(self.tenant.id),
            "--json",
            stdout=stdout,
        )
        report = json.loads(stdout.getvalue())

        self.assertEqual(report["schema"], "grc-audit-integrity-report-v1")
        self.assertTrue(report["ok"])
        self.assertEqual(report["scope_count"], 1)
        self.assertEqual(report["event_count"], 1)

    def test_verification_command_fails_closed_on_tamper(self):
        event = record_audit_event(self.user, self.tenant, "tenant.update", "tenant", self.tenant.id)
        AuditEvent.system_objects.filter(pk=event.pk).update(object_repr="database-tamper")

        with self.assertRaises(CommandError):
            call_command(
                "verify_audit_integrity",
                "--tenant-id",
                str(self.tenant.id),
                "--json",
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )

    @override_settings(APP_ENV="production", AUDIT_INTEGRITY_KEY="")
    def test_production_requires_dedicated_integrity_key(self):
        with patch.dict(os.environ, {"AUDIT_INTEGRITY_KEY": ""}, clear=False):
            with self.assertRaises(AuditIntegrityConfigurationError):
                integrity_key_bytes()


class AuditSiemExportTests(AuditTrailTests):
    def test_siem_export_omits_customer_payload_fields(self):
        record_audit_event(
            self.user,
            self.tenant,
            "evidence.update",
            "evidence",
            self.tenant.id,
            old_data={"secret": "OLD-CUSTOMER-PAYLOAD"},
            new_data={"secret": "NEW-CUSTOMER-PAYLOAD"},
            metadata={"raw": "METADATA-CUSTOMER-PAYLOAD"},
        )
        response = self.client.get("/api/v1/audit-events/export/?after_sequence=0&limit=100")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["events"]), 1)

        event = response.data["events"][0]
        rendered = json.dumps(event)
        self.assertNotIn("old_data", event)
        self.assertNotIn("new_data", event)
        self.assertNotIn("metadata", event)
        self.assertNotIn("OLD-CUSTOMER-PAYLOAD", rendered)
        self.assertNotIn("NEW-CUSTOMER-PAYLOAD", rendered)
        self.assertNotIn("METADATA-CUSTOMER-PAYLOAD", rendered)
        self.assertEqual(event["chain_sequence"], 1)
        self.assertTrue(event["integrity"]["event_hash"])

    def test_siem_jsonl_export_is_bounded_and_cursor_driven(self):
        first = record_audit_event(
            self.user, self.tenant, "tenant.update", "tenant", self.tenant.id
        )
        second = record_audit_event(
            self.user, self.tenant, "tenant.update", "tenant", self.tenant.id
        )

        response = self.client.get(
            "/api/v1/audit-events/export/?after_sequence=0&limit=1&format=jsonl"
        )
        self.assertEqual(response.status_code, 200)
        lines = [line for line in response.content.decode("utf-8").splitlines() if line]
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["event_id"], str(first.id))
        self.assertEqual(response["X-GRC-Next-After-Sequence"], "1")
        self.assertEqual(response["X-GRC-Has-More"], "1")

        next_response = self.client.get(
            "/api/v1/audit-events/export/?after_sequence=1&limit=1&format=jsonl"
        )
        next_payload = json.loads(next_response.content.decode("utf-8").strip())
        self.assertEqual(next_payload["event_id"], str(second.id))
        self.assertEqual(next_response["X-GRC-Has-More"], "0")

    def test_siem_export_does_not_cross_tenant_boundary(self):
        User = get_user_model()
        other_user = User.objects.create_user(
            username="siem-other", password="StrongPassword123!"
        )
        other_tenant = Tenant.objects.create(name="Other SIEM", code="other-siem")
        TenantMembership.objects.create(
            tenant=other_tenant, user=other_user, role_code="admin"
        )
        bootstrap_tenant_rbac(other_tenant, admin_user=other_user)
        foreign = record_audit_event(
            other_user,
            other_tenant,
            "tenant.update",
            "tenant",
            other_tenant.id,
        )
        local = record_audit_event(
            self.user,
            self.tenant,
            "tenant.update",
            "tenant",
            self.tenant.id,
        )

        response = self.client.get("/api/v1/audit-events/export/")
        ids = {row["event_id"] for row in response.data["events"]}
        self.assertIn(str(local.id), ids)
        self.assertNotIn(str(foreign.id), ids)

    def test_siem_export_rejects_unbounded_limit(self):
        response = self.client.get("/api/v1/audit-events/export/?limit=1001")
        self.assertEqual(response.status_code, 400)
