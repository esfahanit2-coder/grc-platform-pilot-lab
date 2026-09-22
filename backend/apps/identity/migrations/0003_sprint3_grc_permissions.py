from django.db import migrations

def add_permissions(apps,schema_editor):
    Permission=apps.get_model('identity','Permission');Role=apps.get_model('identity','Role');RolePermission=apps.get_model('identity','RolePermission')
    catalog=[
        ('control.view','control','View common control library'),('control.manage','control','Manage tenant control definitions and mappings'),('control.implementation.view','control','View control implementations in assigned scope'),('control.implementation.manage','control','Manage control implementations in assigned scope'),
        ('asset.view','asset','View asset register in assigned scope'),('asset.manage','asset','Manage assets in assigned scope'),('risk.view','risk','View risks and methodologies in assigned scope'),('risk.manage','risk','Create and manage risks in assigned scope'),('risk.evaluate','risk','Evaluate risk using approved methodologies'),('risk.treatment.manage','risk','Manage and approve risk treatments'),('action.view','action','View GRC actions in assigned scope'),('action.manage','action','Manage GRC actions in assigned scope')]
    perms={}
    for code,module,description in catalog:
        p,_=Permission.objects.get_or_create(code=code,defaults={'module':module,'name':code.replace('.',' ').title(),'description':description});perms[code]=p
    for role in Role.objects.filter(code='tenant_admin'):
        for p in perms.values(): RolePermission.objects.get_or_create(role=role,permission=p)
    manager_codes=list(perms)
    for role in Role.objects.filter(code='grc_manager'):
        for code in manager_codes: RolePermission.objects.get_or_create(role=role,permission=perms[code])
    for role in Role.objects.filter(code__in=['auditor','viewer']):
        for code in ['control.view','control.implementation.view','asset.view','risk.view','action.view']: RolePermission.objects.get_or_create(role=role,permission=perms[code])
    tenant_ids=Role.objects.values_list('tenant_id',flat=True).distinct()
    for tenant_id in tenant_ids:
        for role_code,name,codes in [
            ('risk_manager','Risk Manager',['tenant.view','organization.view','framework.view','framework.mapping.view','control.view','control.implementation.view','control.implementation.manage','asset.view','asset.manage','risk.view','risk.manage','risk.evaluate','risk.treatment.manage','action.view','action.manage']),
            ('control_owner','Control Owner',['tenant.view','organization.view','framework.view','control.view','control.implementation.view','control.implementation.manage','asset.view','risk.view','action.view','action.manage'])]:
            role,_=Role.objects.get_or_create(tenant_id=tenant_id,code=role_code,defaults={'name':name,'is_system':True})
            for code in codes:
                permission=perms.get(code) or Permission.objects.filter(code=code).first()
                if permission: RolePermission.objects.get_or_create(role=role,permission=permission)

class Migration(migrations.Migration):
    dependencies=[('identity','0002_framework_permissions')]
    operations=[migrations.RunPython(add_permissions,migrations.RunPython.noop)]
