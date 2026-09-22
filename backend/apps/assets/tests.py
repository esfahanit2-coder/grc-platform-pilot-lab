from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant,TenantMembership
from .models import Asset
User=get_user_model()
class AssetTests(APITestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='asset-admin',password='StrongPassword123!');self.other=User.objects.create_user(username='asset-other',password='StrongPassword123!')
        self.tenant=Tenant.objects.create(name='Tenant A',code='asset-a');self.other_tenant=Tenant.objects.create(name='Tenant B',code='asset-b');TenantMembership.objects.create(tenant=self.tenant,user=self.user,role_code='admin');TenantMembership.objects.create(tenant=self.other_tenant,user=self.other,role_code='admin')
        self.unit=OrganizationUnit.objects.create(tenant=self.tenant,unit_type='company',code='A',name='A',manager=self.user);self.other_unit=OrganizationUnit.objects.create(tenant=self.other_tenant,unit_type='company',code='B',name='B',manager=self.other)
        token=str(RefreshToken.for_user(self.user).access_token);self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}');self.headers={'HTTP_X_TENANT_ID':str(self.tenant.id)}
    def test_asset_is_tenant_scoped(self):
        response=self.client.post('/api/v1/assets/',{'organization_unit':str(self.unit.id),'asset_type':'application','code':'APP-1','title':'App','owner':self.user.id,'confidentiality':5,'integrity':4,'availability':4,'criticality':'4.3'},format='json',**self.headers);self.assertEqual(response.status_code,201)
        Asset.objects.create(tenant=self.other_tenant,organization_unit=self.other_unit,asset_type='application',code='B-APP',title='Other',owner=self.other)
        rows=self.client.get('/api/v1/assets/',**self.headers).json()['results'];self.assertEqual([r['code'] for r in rows],['APP-1'])
