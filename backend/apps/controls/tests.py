from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from apps.audit.models import AuditEvent
from apps.frameworks.models import Framework,FrameworkVersion,Requirement
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant,TenantMembership
from .models import Control,ControlImplementation,ControlRequirement
User=get_user_model()
class ControlEngineTests(APITestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='control-admin',password='StrongPassword123!');self.other=User.objects.create_user(username='other',password='StrongPassword123!')
        self.tenant=Tenant.objects.create(name='Tenant A',code='ctl-a');self.tenant_b=Tenant.objects.create(name='Tenant B',code='ctl-b')
        TenantMembership.objects.create(tenant=self.tenant,user=self.user,role_code='admin');TenantMembership.objects.create(tenant=self.tenant_b,user=self.other,role_code='admin')
        self.unit=OrganizationUnit.objects.create(tenant=self.tenant,unit_type='company',code='A',name='Company A',manager=self.user);self.unit_b=OrganizationUnit.objects.create(tenant=self.tenant_b,unit_type='company',code='B',name='Company B',manager=self.other)
        token=str(RefreshToken.for_user(self.user).access_token);self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}');self.headers={'HTTP_X_TENANT_ID':str(self.tenant.id)}
        self.fw1=Framework.objects.create(tenant=self.tenant,code='fw1',name='FW1');self.v1=FrameworkVersion.objects.create(framework=self.fw1,version_code='1');self.r1=Requirement.objects.create(framework_version=self.v1,code='1',title='Requirement 1')
        self.fw2=Framework.objects.create(tenant=self.tenant,code='fw2',name='FW2');self.v2=FrameworkVersion.objects.create(framework=self.fw2,version_code='1');self.r2=Requirement.objects.create(framework_version=self.v2,code='2',title='Requirement 2')
    def test_one_control_maps_to_multiple_frameworks(self):
        c=Control.objects.create(tenant=self.tenant,code='IAM-001',title='MFA',status='active',created_by=self.user)
        for req in [self.r1,self.r2]:
            response=self.client.post('/api/v1/control-requirements/',{'control':str(c.id),'requirement':str(req.id),'coverage':'100','mapping_type':'strong'},format='json',**self.headers);self.assertEqual(response.status_code,201);self.assertFalse(response.json()['approved'])
        self.assertEqual(ControlRequirement.objects.filter(control=c,tenant=self.tenant).values('requirement__framework_version__framework').distinct().count(),2)
    def test_common_control_mapping_requires_explicit_audited_approval(self):
        c=Control.objects.create(tenant=self.tenant,code='GOV-001',title='Governance ownership',status='active',created_by=self.user)
        created=self.client.post('/api/v1/control-requirements/',{'control':str(c.id),'requirement':str(self.r1.id),'coverage':'100','mapping_type':'strong','source':'human-reviewed-crosswalk','rationale':'Pilot crosswalk provenance','approved':True},format='json',**self.headers)
        self.assertEqual(created.status_code,201);self.assertFalse(created.json()['approved'])
        mapping_id=created.json()['id']
        approved=self.client.post(f'/api/v1/control-requirements/{mapping_id}/approve/',{},format='json',**self.headers)
        self.assertEqual(approved.status_code,200);self.assertTrue(approved.json()['approved'])
        event=AuditEvent.objects.get(tenant=self.tenant,action='control_requirement.approve',object_id=mapping_id)
        self.assertEqual(event.actor,self.user);self.assertEqual(event.new_data['approved'],True);self.assertEqual(event.new_data['source'],'human-reviewed-crosswalk')
        changed=self.client.patch(f'/api/v1/control-requirements/{mapping_id}/',{'rationale':'Updated rationale'},format='json',**self.headers)
        self.assertEqual(changed.status_code,200);self.assertFalse(changed.json()['approved'])
    def test_cross_tenant_implementation_is_rejected(self):
        c=Control.objects.create(tenant=self.tenant,code='CTL-1',title='Control',status='active',created_by=self.user)
        response=self.client.post('/api/v1/control-implementations/',{'control':str(c.id),'organization_unit':str(self.unit_b.id),'owner':self.user.id,'implementation_status':'implemented','effectiveness':'effective'},format='json',**self.headers)
        self.assertEqual(response.status_code,400)
    def test_global_control_is_read_only_but_implementable(self):
        g=Control.objects.create(tenant=None,code='GLOBAL-1',title='Global',status='active')
        patch=self.client.patch(f'/api/v1/controls/{g.id}/',{'title':'Changed'},format='json',**self.headers);self.assertEqual(patch.status_code,403)
        create=self.client.post('/api/v1/control-implementations/',{'control':str(g.id),'organization_unit':str(self.unit.id),'owner':self.user.id,'implementation_status':'implemented','effectiveness':'effective'},format='json',**self.headers);self.assertEqual(create.status_code,201)
