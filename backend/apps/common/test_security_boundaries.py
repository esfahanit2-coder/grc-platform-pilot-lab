from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.ai_gateway.models import AIProviderConfig
from apps.documents.models import Document
from apps.evidence.models import Evidence
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership


class CrossTenantIDORRegressionTests(APITestCase):
    def setUp(self):
        User=get_user_model()
        self.user_a=User.objects.create_user(username='tenant-a-admin',password='StrongPassword123!')
        self.user_b=User.objects.create_user(username='tenant-b-admin',password='StrongPassword123!')
        self.tenant_a=Tenant.objects.create(name='Tenant A Security',code='sec-a')
        self.tenant_b=Tenant.objects.create(name='Tenant B Security',code='sec-b')
        TenantMembership.objects.create(tenant=self.tenant_a,user=self.user_a,role_code='admin')
        TenantMembership.objects.create(tenant=self.tenant_b,user=self.user_b,role_code='admin')
        self.unit_b=OrganizationUnit.objects.create(tenant=self.tenant_b,unit_type='company',code='B',name='Tenant B Unit')
        self.evidence_b=Evidence.objects.create(tenant=self.tenant_b,organization_unit=self.unit_b,title='Tenant B Secret Evidence',evidence_type='text',text_content='secret B',owner=self.user_b,storage_key='tenant-b/secret.bin',metadata={'malware_scan_status':'clean'})
        self.document_b=Document.objects.create(tenant=self.tenant_b,organization_unit=self.unit_b,document_type='policy',code='B-POL',title='Tenant B Policy',owner=self.user_b)
        self.provider_b=AIProviderConfig.objects.create(tenant=self.tenant_b,name='Tenant B AI',provider_type='mock',model_name='mock',is_default=True)
        token=str(RefreshToken.for_user(self.user_a).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}',HTTP_X_TENANT_ID=str(self.tenant_a.id))

    def test_direct_foreign_object_ids_are_not_disclosed(self):
        urls=[
            f'/api/v1/evidence/{self.evidence_b.id}/',
            f'/api/v1/evidence/{self.evidence_b.id}/download/',
            f'/api/v1/documents/{self.document_b.id}/',
            f'/api/v1/ai/providers/{self.provider_b.id}/',
        ]
        for url in urls:
            with self.subTest(url=url):
                response=self.client.get(url)
                self.assertEqual(response.status_code,404)

    def test_foreign_object_id_cannot_be_patched_through_tenant_a(self):
        attempts=[
            (f'/api/v1/evidence/{self.evidence_b.id}/',{'title':'stolen'}),
            (f'/api/v1/documents/{self.document_b.id}/',{'title':'stolen'}),
            (f'/api/v1/ai/providers/{self.provider_b.id}/',{'name':'stolen'}),
        ]
        for url,payload in attempts:
            with self.subTest(url=url):
                response=self.client.patch(url,payload,format='json')
                self.assertEqual(response.status_code,404)
        self.evidence_b.refresh_from_db();self.document_b.refresh_from_db();self.provider_b.refresh_from_db()
        self.assertEqual(self.evidence_b.title,'Tenant B Secret Evidence')
        self.assertEqual(self.document_b.title,'Tenant B Policy')
        self.assertEqual(self.provider_b.name,'Tenant B AI')
