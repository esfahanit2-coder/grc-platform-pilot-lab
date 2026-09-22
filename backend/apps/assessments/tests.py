from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.frameworks.models import Framework, FrameworkVersion, Requirement
from apps.identity.models import UserRoleScope
from apps.identity.services import bootstrap_tenant_rbac
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership
from .models import Assessment, AssessmentItem

User=get_user_model()

class AssessmentComplianceTests(APITestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='compliance-admin',password='StrongPassword123!')
        self.tenant=Tenant.objects.create(name='Tenant A',code='assess-a')
        TenantMembership.objects.create(tenant=self.tenant,user=self.user,role_code='admin')
        self.unit=OrganizationUnit.objects.create(tenant=self.tenant,unit_type='company',code='A',name='Company A',manager=self.user)
        self.framework=Framework.objects.create(tenant=self.tenant,code='demo-assess',name='Demo Assess',status='active')
        self.version=FrameworkVersion.objects.create(framework=self.framework,version_code='1',status='active')
        self.req1=Requirement.objects.create(framework_version=self.version,code='1.1',title='Requirement 1',weight=1)
        self.req2=Requirement.objects.create(framework_version=self.version,code='1.2',title='Requirement 2',weight=2)
        self.req3=Requirement.objects.create(framework_version=self.version,code='1.3',title='Heading',assessable=False)
        token=str(RefreshToken.for_user(self.user).access_token);self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}');self.headers={'HTTP_X_TENANT_ID':str(self.tenant.id)}

    def test_create_assessment_locks_version_and_snapshots_assessable_requirements(self):
        r=self.client.post('/api/v1/assessments/',{'framework_version':str(self.version.id),'organization_unit':str(self.unit.id),'title':'ISO readiness','assessment_type':'compliance','owner':self.user.id},format='json',**self.headers)
        self.assertEqual(r.status_code,201)
        self.version.refresh_from_db();self.assertTrue(self.version.is_locked)
        assessment=Assessment.objects.get(id=r.json()['id'])
        self.assertEqual(assessment.items.count(),2)
        item=assessment.items.get(requirement=self.req1)
        self.assertEqual(item.requirement_code_snapshot,'1.1');self.assertEqual(item.requirement_title_snapshot,'Requirement 1')

    def test_weighted_compliance_and_progress_recalculate(self):
        r=self.client.post('/api/v1/assessments/',{'framework_version':str(self.version.id),'organization_unit':str(self.unit.id),'title':'Assessment','owner':self.user.id},format='json',**self.headers)
        aid=r.json()['id'];items=self.client.get(f'/api/v1/assessment-items/?assessment={aid}',**self.headers).json()['results']
        first,second=items
        self.client.patch(f"/api/v1/assessment-items/{first['id']}/",{'status':'compliant'},format='json',**self.headers)
        self.client.patch(f"/api/v1/assessment-items/{second['id']}/",{'status':'partial'},format='json',**self.headers)
        summary=self.client.get(f'/api/v1/assessments/{aid}/summary/',**self.headers).json()
        self.assertEqual(summary['progress_percent'],'100.000')
        self.assertEqual(summary['overall_score'],'66.667')

    def test_scoped_compliance_manager_cannot_see_other_unit(self):
        other=OrganizationUnit.objects.create(tenant=self.tenant,unit_type='department',code='B',name='Other',manager=self.user)
        a=Assessment.objects.create(tenant=self.tenant,framework_version=self.version,organization_unit=other,title='Other',owner=self.user,status='in_progress')
        scoped=User.objects.create_user(username='compliance-scope',password='StrongPassword123!');TenantMembership.objects.create(tenant=self.tenant,user=scoped,role_code='member')
        roles=bootstrap_tenant_rbac(self.tenant);UserRoleScope.objects.create(tenant=self.tenant,user=scoped,role=roles['compliance_manager'],organization_unit=self.unit,is_active=True)
        token=str(RefreshToken.for_user(scoped).access_token);self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        rows=self.client.get('/api/v1/assessments/',**self.headers).json()['results']
        self.assertNotIn(str(a.id),{x['id'] for x in rows})
