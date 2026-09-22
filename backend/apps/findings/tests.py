from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.actions.models import Action
from apps.assessments.models import Assessment, AssessmentItem
from apps.frameworks.models import Framework, FrameworkVersion, Requirement
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant, TenantMembership
from .models import Finding

User=get_user_model()

class FindingCapaTests(APITestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='finding-admin',password='StrongPassword123!');self.tenant=Tenant.objects.create(name='Tenant A',code='finding-a');TenantMembership.objects.create(tenant=self.tenant,user=self.user,role_code='admin')
        self.unit=OrganizationUnit.objects.create(tenant=self.tenant,unit_type='company',code='A',name='Company A',manager=self.user)
        fw=Framework.objects.create(tenant=self.tenant,code='find-fw',name='Finding FW',status='active');ver=FrameworkVersion.objects.create(framework=fw,version_code='1',status='active',is_locked=True);req=Requirement.objects.create(framework_version=ver,code='1.1',title='Access policy')
        assessment=Assessment.objects.create(tenant=self.tenant,framework_version=ver,organization_unit=self.unit,title='Assessment',owner=self.user,status='in_progress');self.item=AssessmentItem.objects.create(assessment=assessment,requirement=req,requirement_code_snapshot='1.1',requirement_title_snapshot='Access policy')
        token=str(RefreshToken.for_user(self.user).access_token);self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}');self.headers={'HTTP_X_TENANT_ID':str(self.tenant.id)}

    def test_finding_inherits_assessment_scope_and_requirement(self):
        r=self.client.post('/api/v1/findings/',{'assessment_item':str(self.item.id),'finding_type':'non_conformity','title':'Missing policy','severity':'high','owner':self.user.id},format='json',**self.headers)
        self.assertEqual(r.status_code,201);finding=Finding.objects.get(id=r.json()['id']);self.assertEqual(finding.organization_unit,self.unit);self.assertEqual(finding.requirement,self.item.requirement)

    def test_close_requires_corrective_actions_complete(self):
        finding=Finding.objects.create(tenant=self.tenant,organization_unit=self.unit,assessment_item=self.item,requirement=self.item.requirement,title='Gap',owner=self.user,severity='high')
        a=self.client.post(f'/api/v1/findings/{finding.id}/actions/',{'title':'Fix gap','owner':self.user.id,'priority':'high'},format='json',**self.headers);self.assertEqual(a.status_code,201)
        close=self.client.post(f'/api/v1/findings/{finding.id}/close/',{'comment':'verified'},format='json',**self.headers);self.assertEqual(close.status_code,400)
        action=Action.objects.get(id=a.json()['id']);action.status=Action.Status.DONE;action.progress=100;action.save()
        close=self.client.post(f'/api/v1/findings/{finding.id}/close/',{'comment':'verified'},format='json',**self.headers);self.assertEqual(close.status_code,200);self.assertEqual(close.json()['status'],'closed')
