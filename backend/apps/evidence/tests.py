from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.assessments.models import Assessment, AssessmentItem
from apps.audit.models import AuditEvent
from apps.frameworks.models import Framework, FrameworkVersion, Requirement
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership
from .models import Evidence, EvidenceLink
from .services import store_uploaded_evidence

User=get_user_model()

class EvidenceTests(APITestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='evidence-admin',password='StrongPassword123!');self.tenant=Tenant.objects.create(name='Tenant A',code='evidence-a');TenantMembership.objects.create(tenant=self.tenant,user=self.user,role_code='admin')
        self.unit=OrganizationUnit.objects.create(tenant=self.tenant,unit_type='company',code='A',name='Company A',manager=self.user);self.other_unit=OrganizationUnit.objects.create(tenant=self.tenant,unit_type='company',code='B',name='Company B',manager=self.user)
        fw=Framework.objects.create(tenant=self.tenant,code='ev-fw',name='Evidence FW',status='active');ver=FrameworkVersion.objects.create(framework=fw,version_code='1',status='active',is_locked=True);req1=Requirement.objects.create(framework_version=ver,code='1',title='One');req2=Requirement.objects.create(framework_version=ver,code='2',title='Two')
        self.assessment=Assessment.objects.create(tenant=self.tenant,framework_version=ver,organization_unit=self.unit,title='A',owner=self.user,status='in_progress')
        self.item1=AssessmentItem.objects.create(assessment=self.assessment,requirement=req1,requirement_code_snapshot='1',requirement_title_snapshot='One');self.item2=AssessmentItem.objects.create(assessment=self.assessment,requirement=req2,requirement_code_snapshot='2',requirement_title_snapshot='Two')
        self.evidence=Evidence.objects.create(tenant=self.tenant,organization_unit=self.unit,title='Policy',evidence_type='text',text_content='approved',owner=self.user)
        token=str(RefreshToken.for_user(self.user).access_token);self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}');self.headers={'HTTP_X_TENANT_ID':str(self.tenant.id)}

    def test_same_evidence_can_support_multiple_assessment_items(self):
        for item in (self.item1,self.item2):
            r=self.client.post('/api/v1/evidence-links/',{'evidence':str(self.evidence.id),'object_type':'assessment_item','object_id':str(item.id),'relation_type':'proves'},format='json',**self.headers);self.assertEqual(r.status_code,201)
        self.assertEqual(EvidenceLink.objects.filter(evidence=self.evidence).count(),2)

    def test_scoped_evidence_cannot_link_across_units(self):
        other_assessment=Assessment.objects.create(tenant=self.tenant,framework_version=self.assessment.framework_version,organization_unit=self.other_unit,title='B',owner=self.user,status='in_progress')
        other_item=AssessmentItem.objects.create(assessment=other_assessment,requirement=self.item1.requirement,requirement_code_snapshot='1',requirement_title_snapshot='One')
        r=self.client.post('/api/v1/evidence-links/',{'evidence':str(self.evidence.id),'object_type':'assessment_item','object_id':str(other_item.id)},format='json',**self.headers)
        self.assertEqual(r.status_code,400)

    @patch('apps.evidence.services.S3ObjectStorage.put')
    def test_new_upload_cannot_self_assert_clean_scan_status(self, put):
        self.evidence.metadata={'malware_scan_status':'clean'}
        self.evidence.save(update_fields=['metadata','updated_at'])
        uploaded=SimpleUploadedFile('policy.pdf',b'%PDF-synthetic',content_type='application/pdf')
        store_uploaded_evidence(self.evidence,uploaded)
        self.evidence.refresh_from_db()
        self.assertEqual(self.evidence.metadata['malware_scan_status'],'pending')
        self.assertTrue(self.evidence.metadata['malware_scan_required'])
        self.assertEqual(self.evidence.metadata['malware_scan_attempts'],0)
        put.assert_called_once()

    def test_api_client_cannot_forge_clean_malware_scan_status(self):
        self.evidence.metadata={'malware_scan_status':'pending','malware_scan_required':True}
        self.evidence.save(update_fields=['metadata','updated_at'])
        response=self.client.patch(
            f'/api/v1/evidence/{self.evidence.id}/',
            {'metadata':{'malware_scan_status':'clean'}},
            format='json',
            **self.headers,
        )
        self.assertEqual(response.status_code,400)
        self.evidence.refresh_from_db()
        self.assertEqual(self.evidence.metadata['malware_scan_status'],'pending')

    def test_normal_metadata_edit_preserves_server_owned_scan_state(self):
        self.evidence.metadata={
            'business_tag':'old',
            'malware_scan_status':'infected',
            'malware_scan_required':True,
            'malware_scan_signature':'Eicar-Signature',
        }
        self.evidence.save(update_fields=['metadata','updated_at'])
        response=self.client.patch(
            f'/api/v1/evidence/{self.evidence.id}/',
            {'metadata':{'business_tag':'new'}},
            format='json',
            **self.headers,
        )
        self.assertEqual(response.status_code,200)
        self.evidence.refresh_from_db()
        self.assertEqual(self.evidence.metadata['business_tag'],'new')
        self.assertEqual(self.evidence.metadata['malware_scan_status'],'infected')
        self.assertEqual(self.evidence.metadata['malware_scan_signature'],'Eicar-Signature')

    @patch('apps.evidence.services.S3ObjectStorage.put')
    def test_active_html_upload_is_rejected_before_storage(self, put):
        uploaded=SimpleUploadedFile('evidence.html',b'<script>alert(1)</script>',content_type='text/html')
        with self.assertRaisesMessage(Exception,'Active or executable file types are not accepted as evidence'):
            store_uploaded_evidence(self.evidence,uploaded)
        put.assert_not_called()

    @override_settings(EVIDENCE_REQUIRE_CLEAN_DOWNLOAD=True)
    @patch('apps.evidence.views.S3ObjectStorage.presigned_get')
    def test_uncleared_file_download_fails_closed_and_is_audited(self, presigned_get):
        self.evidence.storage_key='tenant/test/evidence.bin';self.evidence.sha256='a'*64;self.evidence.metadata={'malware_scan_status':'pending'};self.evidence.save(update_fields=['storage_key','sha256','metadata','updated_at'])
        response=self.client.get(f'/api/v1/evidence/{self.evidence.id}/download/',**self.headers)
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.data['code'],'EVIDENCE_NOT_CLEARED')
        presigned_get.assert_not_called()
        self.assertTrue(AuditEvent.objects.filter(tenant=self.tenant,action='evidence.download',outcome='denied',object_id=self.evidence.id).exists())

    @override_settings(EVIDENCE_REQUIRE_CLEAN_DOWNLOAD=True)
    @patch('apps.evidence.views.S3ObjectStorage.presigned_get',return_value='https://storage.example/signed')
    def test_clean_file_download_is_allowed_and_audited(self, presigned_get):
        self.evidence.storage_key='tenant/test/evidence.bin';self.evidence.sha256='b'*64;self.evidence.metadata={'malware_scan_status':'clean'};self.evidence.save(update_fields=['storage_key','sha256','metadata','updated_at'])
        response=self.client.get(f'/api/v1/evidence/{self.evidence.id}/download/',**self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['url'],'https://storage.example/signed')
        presigned_get.assert_called_once()
        self.assertTrue(AuditEvent.objects.filter(tenant=self.tenant,action='evidence.download',outcome='success',object_id=self.evidence.id).exists())
