from django.db import migrations

def add_permissions(apps,schema_editor):
    Permission=apps.get_model('identity','Permission');Role=apps.get_model('identity','Role');RolePermission=apps.get_model('identity','RolePermission')
    catalog=[
        ('assessment.view','assessment','View assessments in assigned scope'),('assessment.manage','assessment','Create and manage assessments in assigned scope'),('assessment.perform','assessment','Perform requirement assessments in assigned scope'),('assessment.review','assessment','Review and complete assessments in assigned scope'),
        ('evidence.view','evidence','View reusable evidence in assigned scope'),('evidence.manage','evidence','Create, link and manage evidence in assigned scope'),
        ('finding.view','finding','View findings in assigned scope'),('finding.manage','finding','Create and remediate findings in assigned scope'),('finding.close','finding','Verify and close findings in assigned scope')]
    perms={}
    for code,module,description in catalog:
        p,_=Permission.objects.get_or_create(code=code,defaults={'module':module,'name':code.replace('.',' ').title(),'description':description});perms[code]=p
    grants={
        'tenant_admin':list(perms),
        'grc_manager':list(perms),
        'compliance_manager':list(perms),
        'risk_manager':['assessment.view','assessment.perform','evidence.view','evidence.manage','finding.view','finding.manage'],
        'control_owner':['assessment.view','assessment.perform','evidence.view','evidence.manage','finding.view'],
        'auditor':['assessment.view','assessment.perform','assessment.review','evidence.view','finding.view','finding.manage','finding.close'],
        'viewer':['assessment.view','evidence.view','finding.view'],
    }
    tenant_ids=Role.objects.values_list('tenant_id',flat=True).distinct()
    for tenant_id in tenant_ids:
        role,_=Role.objects.get_or_create(tenant_id=tenant_id,code='compliance_manager',defaults={'name':'Compliance Manager','is_system':True})
    for code,codes in grants.items():
        for role in Role.objects.filter(code=code):
            for permission_code in codes:
                permission=perms.get(permission_code) or Permission.objects.filter(code=permission_code).first()
                if permission: RolePermission.objects.get_or_create(role=role,permission=permission)

class Migration(migrations.Migration):
    dependencies=[('identity','0003_sprint3_grc_permissions')]
    operations=[migrations.RunPython(add_permissions,migrations.RunPython.noop)]
