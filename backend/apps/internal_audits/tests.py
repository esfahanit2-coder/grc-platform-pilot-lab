from django.test import TestCase
class InternalAuditModelSmokeTests(TestCase):
    def test_module_imports(self):
        from .models import AuditPlan,AuditEngagement,Workpaper
        self.assertTrue(AuditPlan and AuditEngagement and Workpaper)
