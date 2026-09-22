import ipaddress
import json
import os
import socket
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.controls.models import Control, ControlCategory, ControlImplementation
from apps.evidence.models import Evidence, EvidenceLink
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership

from .clients import ConnectorResult, _normalize_ip, validate_http_base_url
from .models import ConnectorConfig, ConnectorRun
from .normalizers import (
    normalize_active_directory,
    normalize_fortigate,
    normalize_tenable,
    normalize_veeam,
)
from .serializers import ConnectorConfigSerializer
from .services import run_connector


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "provider_contracts.json"


class ConnectorEvidenceTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Pilot", code="pilot-connectors")
        self.user = get_user_model().objects.create_user(username="pilotconn", password="Password12345!")
        TenantMembership.objects.create(tenant=self.tenant, user=self.user, role_code="admin")
        self.unit = OrganizationUnit.objects.create(
            tenant=self.tenant,
            unit_type="company",
            code="HQ",
            name="HQ",
        )

    @patch("apps.connectors.services.connector_for")
    def test_all_connector_types_create_reusable_evidence_contract(self, factory):
        factory.return_value.collect.return_value = ConnectorResult(
            "Connector snapshot",
            {
                "schema_version": "1.0",
                "provider": "synthetic",
                "dataset": "contract_test",
                "summary": {"record_count": 1},
                "records": [{"ok": True}],
            },
        )
        connector_types = [
            ConnectorConfig.ConnectorType.FORTIGATE,
            ConnectorConfig.ConnectorType.TENABLE,
            ConnectorConfig.ConnectorType.VEEAM,
            ConnectorConfig.ConnectorType.ACTIVE_DIRECTORY,
        ]
        for index, connector_type in enumerate(connector_types):
            cfg = ConnectorConfig.objects.create(
                tenant=self.tenant,
                organization_unit=self.unit,
                name=f"connector-{index}",
                connector_type=connector_type,
                base_url="https://connector.example",
                username_env_var="CONNECTOR_USER",
                secret_env_var="CONNECTOR_SECRET",
                configuration={"host": "ad.example", "base_dn": "DC=example,DC=com"}
                if connector_type == ConnectorConfig.ConnectorType.ACTIVE_DIRECTORY
                else {},
            )
            run, evidence = run_connector(cfg, user=self.user)
            self.assertEqual(run.status, ConnectorRun.Status.SUCCEEDED)
            self.assertEqual(evidence.tenant, self.tenant)
            self.assertEqual(evidence.metadata["connector_run_id"], str(run.id))
            self.assertEqual(evidence.metadata["collection_mode"], "read_only")
            self.assertTrue(evidence.metadata["human_review_required"])
            self.assertFalse(evidence.metadata["asserts_compliance"])
            self.assertEqual(evidence.metadata["provider_schema_version"], "1.0")
            self.assertEqual(evidence.metadata["dataset"], "contract_test")
            self.assertEqual(evidence.metadata["summary"], {"record_count": 1})
            self.assertEqual(len(evidence.metadata["payload_sha256"]), 64)

        self.assertEqual(Evidence.objects.filter(tenant=self.tenant).count(), 4)

    @patch("apps.connectors.services.connector_for")
    def test_connector_evidence_link_does_not_change_control_effectiveness(self, factory):
        factory.return_value.collect.return_value = ConnectorResult(
            "Connector snapshot",
            {
                "schema_version": "1.0",
                "provider": "fortigate",
                "dataset": "security_configuration",
                "summary": {"policy_count": 2},
            },
        )
        cfg = ConnectorConfig.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            name="FG-link",
            connector_type=ConnectorConfig.ConnectorType.FORTIGATE,
            base_url="https://fg.example",
            secret_env_var="FG_TOKEN",
        )
        _, evidence = run_connector(cfg, user=self.user)
        category = ControlCategory.objects.create(tenant=self.tenant, code="network", name="Network")
        control = Control.objects.create(
            tenant=self.tenant,
            code="NET-1",
            title="Firewall policy governance",
            category=category,
            status=Control.Status.ACTIVE,
            created_by=self.user,
        )
        implementation = ControlImplementation.objects.create(
            tenant=self.tenant,
            control=control,
            organization_unit=self.unit,
            owner=self.user,
        )
        EvidenceLink.objects.create(
            tenant=self.tenant,
            evidence=evidence,
            object_type="control_implementation",
            object_id=implementation.id,
            relation_type=EvidenceLink.RelationType.SUPPORTS,
        )
        implementation.refresh_from_db()
        self.assertEqual(implementation.effectiveness, ControlImplementation.Effectiveness.NOT_ASSESSED)
        self.assertEqual(implementation.implementation_status, ControlImplementation.ImplementationStatus.NOT_IMPLEMENTED)
        self.assertEqual(evidence.links.count(), 1)

    @patch("apps.connectors.services.connector_for")
    def test_failed_sync_is_persisted_and_secret_is_redacted(self, factory):
        cfg = ConnectorConfig.objects.create(
            tenant=self.tenant,
            organization_unit=self.unit,
            name="FG",
            connector_type=ConnectorConfig.ConnectorType.FORTIGATE,
            base_url="https://fg.example",
            secret_env_var="FG_TOKEN",
        )
        factory.return_value.collect.side_effect = RuntimeError("upstream failed with super-secret-token")
        with patch.dict(os.environ, {"FG_TOKEN": "super-secret-token"}):
            with self.assertRaises(RuntimeError):
                run_connector(cfg, user=self.user)

        run = ConnectorRun.objects.get(connector=cfg)
        cfg.refresh_from_db()
        self.assertEqual(run.status, ConnectorRun.Status.FAILED)
        self.assertIn("[REDACTED]", run.error)
        self.assertNotIn("super-secret-token", run.error)
        self.assertEqual(cfg.last_status, "failed")
        self.assertEqual(cfg.last_error, run.error)

    def test_serializer_rejects_literal_secret_reference(self):
        serializer = ConnectorConfigSerializer(
            data={
                "name": "unsafe-secret",
                "connector_type": ConnectorConfig.ConnectorType.FORTIGATE,
                "base_url": "https://fg.example",
                "secret_env_var": "literal-secret!",
                "configuration": {"read_paths": ["/api/v2/cmdb/system/global"]},
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("secret_env_var", serializer.errors)

    def test_serializer_rejects_url_credentials(self):
        serializer = ConnectorConfigSerializer(
            data={
                "name": "unsafe-url",
                "connector_type": ConnectorConfig.ConnectorType.FORTIGATE,
                "base_url": "https://admin:password@fg.example",
                "secret_env_var": "FG_TOKEN",
                "configuration": {"read_paths": ["/api/v2/cmdb/system/global"]},
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("base_url", serializer.errors)

    def test_serializer_rejects_fortigate_host_escape_path(self):
        serializer = ConnectorConfigSerializer(
            data={
                "name": "unsafe-path",
                "connector_type": ConnectorConfig.ConnectorType.FORTIGATE,
                "base_url": "https://fg.example",
                "secret_env_var": "FG_TOKEN",
                "configuration": {"read_paths": ["https://evil.example/api/v2/cmdb/system/global"]},
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("configuration", serializer.errors)

    def test_serializer_rejects_unknown_fortigate_profile(self):
        serializer = ConnectorConfigSerializer(
            data={
                "name": "bad-profile",
                "connector_type": ConnectorConfig.ConnectorType.FORTIGATE,
                "base_url": "https://fg.example",
                "secret_env_var": "FG_TOKEN",
                "configuration": {"collection_profile": "write-everything"},
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("configuration", serializer.errors)

    def test_normalize_ipv4_mapped_ipv6(self):
        self.assertEqual(_normalize_ip("10.10.20.30"), ipaddress.ip_address("10.10.20.30"))
        self.assertEqual(_normalize_ip("::ffff:10.10.20.30"), ipaddress.ip_address("10.10.20.30"))

    @patch("apps.connectors.clients.socket.getaddrinfo")
    def test_http_target_blocks_loopback(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
        with self.assertRaises(ValidationError):
            validate_http_base_url("https://connector.example")

    @patch("apps.connectors.clients.socket.getaddrinfo")
    def test_http_target_allows_private_on_prem_address(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.10.20.30", 443)),
        ]
        parsed = validate_http_base_url("https://connector.example")
        self.assertEqual(parsed.hostname, "connector.example")


class ProviderNormalizationContractTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fortigate_fixture_normalizes_to_security_facts(self):
        payload = normalize_fortigate(self.fixture["fortigate"]["paths"])
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["provider"], "fortigate")
        self.assertEqual(payload["dataset"], "security_configuration")
        self.assertEqual(payload["device"]["hostname"], "fg-pilot")
        self.assertEqual(payload["summary"]["admin_count"], 2)
        self.assertEqual(payload["summary"]["admins_with_two_factor_count"], 1)
        self.assertEqual(payload["summary"]["policy_count"], 2)
        self.assertEqual(payload["summary"]["enabled_policy_count"], 1)
        self.assertEqual(payload["summary"]["policies_with_logging_count"], 1)
        self.assertEqual(payload["summary"]["interface_count"], 2)
        self.assertEqual(payload["summary"]["interface_up_count"], 1)

    def test_tenable_fixture_normalizes_scan_inventory(self):
        payload = normalize_tenable(self.fixture["tenable"]["scans"])
        self.assertEqual(payload["provider"], "tenable")
        self.assertEqual(payload["dataset"], "scan_inventory")
        self.assertEqual(payload["summary"]["scan_count"], 3)
        self.assertEqual(
            payload["summary"]["status_counts"],
            {"canceled": 1, "completed": 1, "running": 1},
        )
        self.assertEqual(payload["summary"]["most_recent_modification"], 1760000200)

    def test_veeam_fixture_normalizes_backup_assurance(self):
        payload = normalize_veeam(
            self.fixture["veeam"]["backups"],
            self.fixture["veeam"]["sessions"],
        )
        self.assertEqual(payload["provider"], "veeam")
        self.assertEqual(payload["dataset"], "backup_assurance")
        self.assertEqual(payload["summary"]["backup_count"], 2)
        self.assertEqual(payload["summary"]["session_count"], 2)
        self.assertEqual(payload["summary"]["session_result_counts"], {"success": 1, "warning": 1})
        self.assertEqual(payload["summary"]["session_state_counts"], {"stopped": 2})

    def test_active_directory_fixture_normalizes_account_hygiene(self):
        fixture = self.fixture["active_directory"]
        payload = normalize_active_directory(
            fixture["rows"],
            privileged_groups=fixture["privileged_groups"],
            include_sample=False,
        )
        self.assertEqual(payload["provider"], "active_directory")
        self.assertEqual(payload["dataset"], "account_hygiene")
        self.assertEqual(payload["summary"]["user_count"], 4)
        self.assertEqual(payload["summary"]["disabled_count"], 1)
        self.assertEqual(payload["summary"]["password_not_required_count"], 1)
        self.assertEqual(payload["summary"]["password_never_expires_count"], 1)
        self.assertEqual(payload["summary"]["privileged_user_count"], 1)
        self.assertNotIn("sample", payload)

    def test_active_directory_sample_is_explicit_opt_in(self):
        fixture = self.fixture["active_directory"]
        payload = normalize_active_directory(
            fixture["rows"],
            privileged_groups=fixture["privileged_groups"],
            include_sample=True,
        )
        self.assertEqual(len(payload["sample"]), 4)
        self.assertEqual(payload["sample"][0]["account"], "alice")
