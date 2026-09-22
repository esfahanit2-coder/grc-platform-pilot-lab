import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenancy.models import Tenant, TenantMembership
from .models import Framework, FrameworkVersion, Requirement, RequirementMapping

User = get_user_model()


class FrameworkEngineTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="framework-admin", password="StrongPassword123!")
        self.tenant = Tenant.objects.create(name="Tenant A", code="tenant-a")
        self.other_tenant = Tenant.objects.create(name="Tenant B", code="tenant-b")
        TenantMembership.objects.create(tenant=self.tenant, user=self.user, role_code="admin")
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.headers = {"HTTP_X_TENANT_ID": str(self.tenant.id)}

        self.global_framework = Framework.objects.create(
            tenant=None, code="public-demo", name="Public Demo", status="active", license_type="public", content_source="built_in"
        )
        self.global_version = FrameworkVersion.objects.create(framework=self.global_framework, version_code="1", status="active", is_locked=True)
        self.global_req = Requirement.objects.create(framework_version=self.global_version, code="G.1", title="Global requirement")

        self.local_framework = Framework.objects.create(tenant=self.tenant, code="local-demo", name="Local Demo")
        self.local_version = FrameworkVersion.objects.create(framework=self.local_framework, version_code="1")
        self.local_req = Requirement.objects.create(framework_version=self.local_version, code="L.1", title="Local requirement")
        self.other_framework = Framework.objects.create(tenant=self.other_tenant, code="other", name="Other")
        self.other_version = FrameworkVersion.objects.create(framework=self.other_framework, version_code="1")
        self.other_req = Requirement.objects.create(framework_version=self.other_version, code="O.1", title="Other requirement")

    def test_list_contains_global_and_local_but_not_other_tenant(self):
        response = self.client.get("/api/v1/frameworks/", **self.headers)
        self.assertEqual(response.status_code, 200)
        codes = {row["code"] for row in response.json()["results"]}
        self.assertEqual(codes, {"public-demo", "local-demo"})

    def test_global_framework_is_read_only_for_tenant(self):
        response = self.client.patch(
            f"/api/v1/frameworks/{self.global_framework.id}/",
            {"name": "Changed"}, format="json", **self.headers,
        )
        self.assertEqual(response.status_code, 403)
        self.global_framework.refresh_from_db()
        self.assertEqual(self.global_framework.name, "Public Demo")

    def test_locked_version_blocks_requirement_update(self):
        response = self.client.patch(
            f"/api/v1/requirements/{self.global_req.id}/",
            {"title": "Changed"}, format="json", **self.headers,
        )
        self.assertIn(response.status_code, {400, 403})

        lock_response = self.client.post(f"/api/v1/framework-versions/{self.local_version.id}/lock/", {}, format="json", **self.headers)
        self.assertEqual(lock_response.status_code, 200)
        response = self.client.patch(
            f"/api/v1/requirements/{self.local_req.id}/",
            {"title": "Changed"}, format="json", **self.headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_cross_tenant_mapping_is_rejected(self):
        response = self.client.post(
            "/api/v1/requirement-mappings/",
            {"source_requirement": str(self.local_req.id), "target_requirement": str(self.other_req.id), "mapping_type": "related"},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(RequirementMapping.objects.filter(tenant=self.tenant).exists())

    def test_json_import_dry_run_and_commit(self):
        payload = {
            "framework": {"code": "imported-demo", "name": "Imported Demo", "license_type": "internal"},
            "version": {"version_code": "2026", "title": "2026 release"},
            "requirements": [
                {"code": "1", "title": "Governance", "assessable": False},
                {"code": "1.1", "parent_code": "1", "title": "Define responsibilities", "title_fa": "تعریف مسئولیت‌ها"},
            ],
        }
        upload = SimpleUploadedFile("pack.json", json.dumps(payload, ensure_ascii=False).encode("utf-8"), content_type="application/json")
        preview = self.client.post("/api/v1/frameworks/import/?dry_run=true", {"file": upload}, format="multipart", **self.headers)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["requirements"], 2)
        self.assertFalse(Framework.objects.filter(tenant=self.tenant, code="imported-demo").exists())

        upload = SimpleUploadedFile("pack.json", json.dumps(payload, ensure_ascii=False).encode("utf-8"), content_type="application/json")
        commit = self.client.post("/api/v1/frameworks/import/?dry_run=false", {"file": upload}, format="multipart", **self.headers)
        self.assertEqual(commit.status_code, 201)
        framework = Framework.objects.get(tenant=self.tenant, code="imported-demo")
        version = framework.versions.get(version_code="2026")
        self.assertEqual(version.requirements.count(), 2)
        child = version.requirements.get(code="1.1")
        self.assertEqual(child.parent.code, "1")
        self.assertEqual(child.translations.get(language="fa").title, "تعریف مسئولیت‌ها")

    def test_repository_pilot_pack_imports_with_provenance_and_locks(self):
        pack_path = Path(__file__).resolve().parents[3] / "content-packs" / "examples" / "pilot-isms-security-baseline.json"
        raw = pack_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(payload["framework"]["license_type"], "internal")
        self.assertEqual(payload["framework"]["license_metadata"]["rights_basis"], "Original project-authored content")
        self.assertFalse(payload["framework"]["license_metadata"]["restricted_sources_reproduced"])
        self.assertIn("soa", payload["version"]["metadata"]["report_hooks"])
        self.assertIn("rtp", payload["version"]["metadata"]["report_hooks"])

        upload = SimpleUploadedFile("pilot-isms-security-baseline.json", raw, content_type="application/json")
        committed = self.client.post("/api/v1/frameworks/import/?dry_run=false", {"file": upload}, format="multipart", **self.headers)
        self.assertEqual(committed.status_code, 201)
        framework = Framework.objects.get(tenant=self.tenant, code="pilot-isms-security-baseline")
        version = framework.versions.get(version_code="2026.1")
        self.assertEqual(framework.license_metadata["rights_basis"], "Original project-authored content")
        self.assertEqual(version.requirements.filter(assessable=True).count(), 8)
        self.assertEqual(version.metadata["scoring_model"]["type"], "weighted_assessment")

        locked = self.client.post(f"/api/v1/framework-versions/{version.id}/lock/", {}, format="json", **self.headers)
        self.assertEqual(locked.status_code, 200)
        version.refresh_from_db()
        self.assertTrue(version.is_locked)
        self.assertEqual(len(version.checksum), 64)
        req = version.requirements.get(code="IAM.1")
        blocked = self.client.patch(f"/api/v1/requirements/{req.id}/", {"title": "Changed"}, format="json", **self.headers)
        self.assertEqual(blocked.status_code, 400)

    def test_mapping_can_be_approved_and_is_tenant_owned(self):
        response = self.client.post(
            "/api/v1/requirement-mappings/",
            {"source_requirement": str(self.local_req.id), "target_requirement": str(self.global_req.id), "mapping_type": "strong", "strength": "0.9000", "confidence": "0.8000"},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, 201)
        mapping_id = response.json()["id"]
        approve = self.client.post(f"/api/v1/requirement-mappings/{mapping_id}/approve/", {}, format="json", **self.headers)
        self.assertEqual(approve.status_code, 200)
        mapping = RequirementMapping.objects.get(id=mapping_id)
        self.assertEqual(mapping.tenant, self.tenant)
        self.assertIsNotNone(mapping.approved_at)
