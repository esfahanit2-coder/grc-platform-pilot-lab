from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from apps.actions.models import Action
from apps.assets.models import Asset
from apps.controls.models import Control,ControlImplementation
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant,TenantMembership
from .models import Risk,RiskEvaluation,RiskMethodology,RiskTreatment
from .services import methodology_defaults
User=get_user_model()
class RiskEngineTests(APITestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='risk-admin',password='StrongPassword123!');self.tenant=Tenant.objects.create(name='Tenant A',code='risk-a');TenantMembership.objects.create(tenant=self.tenant,user=self.user,role_code='admin')
        self.unit=OrganizationUnit.objects.create(tenant=self.tenant,unit_type='company',code='A',name='Company A',manager=self.user);self.other_unit=OrganizationUnit.objects.create(tenant=self.tenant,unit_type='department',code='B',name='Other Unit',manager=self.user)
        self.asset=Asset.objects.create(tenant=self.tenant,organization_unit=self.unit,asset_type='application',code='AD-01',title='Active Directory',owner=self.user)
        d=methodology_defaults();self.method=RiskMethodology.objects.create(tenant=self.tenant,name='5x5',likelihood_scale=d['likelihood_scale'],impact_scale=d['impact_scale'],thresholds=d['thresholds'],formula='product',is_default=True)
        self.risk=Risk.objects.create(tenant=self.tenant,organization_unit=self.unit,asset=self.asset,code='R-001',title='Unauthorized Access',scenario='Privileged account compromise',owner=self.user,status='open')
        token=str(RefreshToken.for_user(self.user).access_token);self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}');self.headers={'HTTP_X_TENANT_ID':str(self.tenant.id)}
    def test_risk_evaluation_history_and_levels(self):
        for typ,l,i,expected in [('inherent','5','4','critical'),('residual','2','4','medium'),('target','1','4','low')]:
            r=self.client.post(f'/api/v1/risks/{self.risk.id}/evaluate/',{'methodology':str(self.method.id),'evaluation_type':typ,'likelihood':l,'impact':i},format='json',**self.headers);self.assertEqual(r.status_code,201);self.assertEqual(r.json()['level'],expected)
        self.assertEqual(RiskEvaluation.objects.filter(risk=self.risk).count(),3)
        detail=self.client.get(f'/api/v1/risks/{self.risk.id}/',**self.headers).json();self.assertEqual(detail['latest_evaluations']['residual']['score'],'8.0000')
    def test_control_outside_risk_scope_is_rejected(self):
        c=Control.objects.create(tenant=self.tenant,code='MFA',title='MFA',status='active',created_by=self.user);ci=ControlImplementation.objects.create(tenant=self.tenant,control=c,organization_unit=self.other_unit,owner=self.user,implementation_status='implemented')
        response=self.client.post('/api/v1/risk-controls/',{'risk':str(self.risk.id),'control_implementation':str(ci.id),'relationship_type':'existing'},format='json',**self.headers);self.assertEqual(response.status_code,400)

    def test_scoped_risk_manager_only_sees_assigned_unit(self):
        from apps.identity.services import bootstrap_tenant_rbac
        from apps.identity.models import UserRoleScope
        scoped=User.objects.create_user(username='scoped-risk',password='StrongPassword123!')
        TenantMembership.objects.create(tenant=self.tenant,user=scoped,role_code='member')
        roles=bootstrap_tenant_rbac(self.tenant)
        UserRoleScope.objects.create(tenant=self.tenant,user=scoped,role=roles['risk_manager'],organization_unit=self.unit,is_active=True)
        Risk.objects.create(tenant=self.tenant,organization_unit=self.other_unit,code='R-OTHER',title='Other risk',owner=self.user,status='open')
        token=str(RefreshToken.for_user(scoped).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        rows=self.client.get('/api/v1/risks/',**self.headers).json()['results']
        self.assertEqual({r['code'] for r in rows},{'R-001'})
    def test_rtp_contains_treatment_action_and_exports_docx(self):
        t=RiskTreatment.objects.create(risk=self.risk,strategy='reduce',description='Deploy MFA',owner=self.user,status='in_progress');Action.objects.create(tenant=self.tenant,organization_unit=self.unit,title='Enable MFA',owner=self.user,source_type='risk_treatment',source_id=t.id,progress=50)
        payload=self.client.get(f'/api/v1/risks/{self.risk.id}/rtp/',**self.headers);self.assertEqual(payload.status_code,200);self.assertEqual(payload.json()['treatments'][0]['actions'][0]['title'],'Enable MFA')
        doc=self.client.get(f'/api/v1/risks/{self.risk.id}/rtp/?format=docx',**self.headers);self.assertEqual(doc.status_code,200);self.assertIn('wordprocessingml',doc['Content-Type'])
