import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.actions.models import Action
from apps.assessments.models import AssessmentItem
from apps.assessments.services import create_assessment, recalculate_assessment
from apps.assets.models import Asset
from apps.audit.models import AuditEvent
from apps.controls.models import Control, ControlCategory, ControlImplementation, ControlRequirement
from apps.documents.exporters import soa_docx
from apps.evidence.models import Evidence, EvidenceLink
from apps.findings.models import Finding
from apps.frameworks.models import Framework
from apps.identity.services import bootstrap_tenant_rbac
from apps.internal_audits.exporters import audit_report_docx
from apps.internal_audits.models import AuditEngagement, Workpaper
from apps.organizations.models import OrganizationUnit
from apps.risks.exporters import rtp_docx_response, rtp_payload
from apps.risks.models import Risk, RiskCategory, RiskControl, RiskEvaluation, RiskMethodology, RiskTreatment
from apps.risks.services import evaluate_risk, methodology_defaults
from apps.tenancy.models import Tenant, TenantMembership


class GoldenPilotScenarioTests(APITestCase):
    def _token(self, user):
        return str(RefreshToken.for_user(user).access_token)

    def test_end_to_end_pilot_scenario(self):
        User = get_user_model()
        user = User.objects.create_user(username="pilot-owner", password="Password12345!")
        viewer = User.objects.create_user(username="pilot-scoped", password="Password12345!")
        tenant = Tenant.objects.create(name="Pilot Organization", code="pilot-org")
        other_tenant = Tenant.objects.create(name="Other Organization", code="other-org")
        TenantMembership.objects.create(tenant=tenant, user=user, role_code="admin")
        TenantMembership.objects.create(tenant=tenant, user=viewer, role_code="member")
        roles = bootstrap_tenant_rbac(tenant, admin_user=user)

        headers = {"HTTP_X_TENANT_ID": str(tenant.id)}
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self._token(user)}")

        create_unit = self.client.post(
            "/api/v1/organization-units/",
            {"unit_type": "company", "code": "HQ", "name": "Head Office"},
            format="json",
            **headers,
        )
        self.assertEqual(create_unit.status_code, 201)
        unit = OrganizationUnit.objects.get(tenant=tenant, code="HQ")
        create_sibling = self.client.post(
            "/api/v1/organization-units/",
            {"unit_type": "company", "code": "BRANCH", "name": "Sibling Branch"},
            format="json",
            **headers,
        )
        self.assertEqual(create_sibling.status_code, 201)

        framework_payload = {
            "framework": {
                "code": "pilot-baseline",
                "name": "Pilot Baseline",
                "publisher": "GRC Platform",
                "license_type": "internal",
            },
            "version": {"version_code": "2026.1", "title": "Pilot"},
            "requirements": [
                {
                    "code": "IAM.1",
                    "title": "Privileged access uses MFA",
                    "body": "Original pilot content",
                    "weight": 1,
                }
            ],
        }
        preview = self.client.post(
            "/api/v1/frameworks/import/?dry_run=true",
            {
                "file": SimpleUploadedFile(
                    "pilot-baseline.json",
                    json.dumps(framework_payload).encode("utf-8"),
                    content_type="application/json",
                )
            },
            format="multipart",
            **headers,
        )
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.data["dry_run"])
        self.assertFalse(Framework.objects.filter(tenant=tenant, code="pilot-baseline").exists())

        imported = self.client.post(
            "/api/v1/frameworks/import/?dry_run=false",
            {
                "file": SimpleUploadedFile(
                    "pilot-baseline.json",
                    json.dumps(framework_payload).encode("utf-8"),
                    content_type="application/json",
                )
            },
            format="multipart",
            **headers,
        )
        self.assertEqual(imported.status_code, 201)
        framework = Framework.objects.get(tenant=tenant, code="pilot-baseline")
        version = framework.versions.get(version_code="2026.1")
        req = version.requirements.get(code="IAM.1")
        lock_version = self.client.post(
            f"/api/v1/framework-versions/{version.id}/lock/",
            {},
            format="json",
            **headers,
        )
        self.assertEqual(lock_version.status_code, 200)
        version.refresh_from_db()
        self.assertTrue(version.is_locked)
        self.assertEqual(version.status, "active")

        category = ControlCategory.objects.create(tenant=tenant, code="iam", name="Identity")
        control = Control.objects.create(
            tenant=tenant,
            code="CTRL-IAM-MFA",
            title="Privileged MFA",
            category=category,
            control_type="technical",
            nature="preventive",
            status="active",
            created_by=user,
        )
        ControlRequirement.objects.create(
            tenant=tenant,
            control=control,
            requirement=req,
            coverage=100,
            mapping_type="strong",
            approved=True,
        )
        impl = ControlImplementation.objects.create(
            tenant=tenant,
            control=control,
            organization_unit=unit,
            owner=user,
            implementation_status="implemented",
            effectiveness="effective",
            implementation_description="MFA enforced for privileged identities",
        )
        asset = Asset.objects.create(
            tenant=tenant,
            organization_unit=unit,
            asset_type="application",
            code="AD-01",
            title="Directory Service",
            owner=user,
            criticality=5,
        )
        risk = Risk.objects.create(
            tenant=tenant,
            organization_unit=unit,
            asset=asset,
            category=RiskCategory.objects.create(tenant=tenant, code="cyber", name="Cyber"),
            code="RISK-001",
            title="Privileged account compromise",
            scenario="A privileged account is compromised.",
            owner=user,
            status="treatment",
        )
        cfg = methodology_defaults()
        method = RiskMethodology.objects.create(
            tenant=tenant,
            name="Pilot 5x5",
            likelihood_scale=cfg["likelihood_scale"],
            impact_scale=cfg["impact_scale"],
            thresholds=cfg["thresholds"],
            formula="product",
            is_default=True,
        )
        inherent = evaluate_risk(
            risk=risk,
            methodology=method,
            evaluation_type=RiskEvaluation.EvaluationType.INHERENT,
            likelihood=5,
            impact=5,
            user=user,
        )
        residual = evaluate_risk(
            risk=risk,
            methodology=method,
            evaluation_type=RiskEvaluation.EvaluationType.RESIDUAL,
            likelihood=2,
            impact=4,
            user=user,
        )
        RiskControl.objects.create(risk=risk, control_implementation=impl, relationship_type="existing")
        treatment = RiskTreatment.objects.create(
            risk=risk,
            strategy="reduce",
            description="Maintain MFA and monitor privileged access.",
            owner=user,
            status="in_progress",
        )
        Action.objects.create(
            tenant=tenant,
            organization_unit=unit,
            title="Quarterly privileged MFA review",
            owner=user,
            priority="high",
            status="in_progress",
            progress=50,
            source_type="risk_treatment",
            source_id=treatment.id,
        )

        assessment = create_assessment(
            tenant=tenant,
            framework_version=version,
            title="Pilot assurance assessment",
            assessment_type="compliance",
            owner=user,
            organization_unit=unit,
        )
        item = assessment.items.get(requirement=req)
        item.status = AssessmentItem.Status.COMPLIANT
        item.applicability = AssessmentItem.Applicability.APPLICABLE
        item.assessor_comment = "MFA implementation verified."
        item.save()
        recalculate_assessment(assessment)
        evidence = Evidence.objects.create(
            tenant=tenant,
            organization_unit=unit,
            title="Privileged MFA configuration snapshot",
            evidence_type="configuration",
            source="pilot",
            owner=user,
            classification="internal",
            text_content="MFA enforcement enabled",
        )
        EvidenceLink.objects.create(
            tenant=tenant,
            evidence=evidence,
            object_type="assessment_item",
            object_id=item.id,
            relation_type="proves",
        )

        engagement = AuditEngagement.objects.create(
            tenant=tenant,
            organization_unit=unit,
            framework_version=version,
            title="Pilot internal audit",
            audit_type=AuditEngagement.AuditType.FRAMEWORK,
            objective="Verify the pilot MFA control and supporting evidence.",
            scope="Head Office privileged access control.",
            lead_auditor=user,
            status=AuditEngagement.Status.COMPLETED,
            conclusion="Pilot audit completed with one improvement observation.",
        )
        engagement.requirements.add(req)
        engagement.controls.add(impl)
        workpaper = Workpaper.objects.create(
            engagement=engagement,
            requirement=req,
            control_implementation=impl,
            title="MFA design and operating effectiveness",
            objective="Confirm privileged identities require MFA.",
            procedure="Inspect configuration evidence and assessment result.",
            sample="Privileged MFA configuration snapshot",
            tester=user,
            result=Workpaper.Result.PARTIAL,
            conclusion="MFA is effective; review evidence collection can be automated.",
            status=Workpaper.Status.REVIEWED,
            reviewed_by=user,
        )
        finding = Finding.objects.create(
            tenant=tenant,
            organization_unit=unit,
            assessment_item=item,
            audit_workpaper=workpaper,
            requirement=req,
            control_implementation=impl,
            risk=risk,
            finding_type="observation",
            title="Extend review automation",
            description="Pilot observation for remediation workflow",
            severity="low",
            owner=user,
        )
        Action.objects.create(
            tenant=tenant,
            organization_unit=unit,
            title="Automate MFA review evidence",
            owner=user,
            priority="medium",
            status="todo",
            source_type="finding",
            source_id=finding.id,
        )

        rtp = rtp_docx_response(risk)
        soa = soa_docx(assessment)
        audit_report = audit_report_docx(engagement)
        self.assertEqual(rtp.status_code, 200)
        self.assertEqual(soa.status_code, 200)
        self.assertEqual(audit_report.status_code, 200)
        self.assertTrue(rtp.content.startswith(b"PK"))
        self.assertTrue(soa.content.startswith(b"PK"))
        self.assertTrue(audit_report.content.startswith(b"PK"))

        assign_scope = self.client.post(
            f"/api/v1/tenant-users/{viewer.id}/role-assignments/",
            {
                "role_code": roles["grc_manager"].code,
                "organization_unit": str(unit.id),
                "is_active": True,
            },
            format="json",
            **headers,
        )
        self.assertEqual(assign_scope.status_code, 201)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self._token(viewer)}")
        scoped_list = self.client.get("/api/v1/organization-units/", **headers)
        self.assertEqual(scoped_list.status_code, 200)
        scoped_codes = {row["code"] for row in scoped_list.data["results"]}
        self.assertIn("HQ", scoped_codes)
        self.assertNotIn("BRANCH", scoped_codes)
        escape_scope = self.client.post(
            "/api/v1/organization-units/",
            {"unit_type": "company", "code": "ESCAPE", "name": "Escaped root"},
            format="json",
            **headers,
        )
        self.assertEqual(escape_scope.status_code, 403)
        cross_tenant = self.client.get(
            "/api/v1/organization-units/",
            HTTP_X_TENANT_ID=str(other_tenant.id),
        )
        self.assertEqual(cross_tenant.status_code, 403)

        assessment.refresh_from_db()
        self.assertEqual(inherent.level, "critical")
        self.assertEqual(residual.level, "medium")
        self.assertEqual(assessment.overall_score, Decimal("100.000"))
        self.assertTrue(EvidenceLink.objects.filter(object_id=item.id).exists())
        rtp_data = rtp_payload(risk)
        self.assertEqual(len(rtp_data["treatments"]), 1)
        self.assertEqual(len(rtp_data["treatments"][0]["actions"]), 1)
        self.assertTrue(Finding.objects.filter(id=finding.id, audit_workpaper=workpaper).exists())

        audit_actions = set(AuditEvent.objects.filter(tenant=tenant).values_list("action", flat=True))
        self.assertIn("organization.create", audit_actions)
        self.assertIn("framework.import", audit_actions)
        self.assertIn("framework_version.lock", audit_actions)
        self.assertIn("role.assign", audit_actions)
