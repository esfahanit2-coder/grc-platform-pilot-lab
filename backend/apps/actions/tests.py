from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant,TenantMembership
from .models import Action
User=get_user_model()
class ActionTests(APITestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='action-admin',password='StrongPassword123!');self.tenant=Tenant.objects.create(name='Tenant A',code='action-a');TenantMembership.objects.create(tenant=self.tenant,user=self.user,role_code='admin');self.unit=OrganizationUnit.objects.create(tenant=self.tenant,unit_type='company',code='A',name='A',manager=self.user);token=str(RefreshToken.for_user(self.user).access_token);self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}');self.headers={'HTTP_X_TENANT_ID':str(self.tenant.id)}
    def test_done_action_sets_progress_and_completion(self):
        a=Action.objects.create(tenant=self.tenant,organization_unit=self.unit,title='Task',owner=self.user);r=self.client.patch(f'/api/v1/actions/{a.id}/',{'status':'done'},format='json',**self.headers);self.assertEqual(r.status_code,200);a.refresh_from_db();self.assertEqual(a.progress,100);self.assertIsNotNone(a.completed_at)
