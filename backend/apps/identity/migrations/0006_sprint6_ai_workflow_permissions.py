from django.db import migrations

def add_permissions(apps,schema_editor):
    Permission=apps.get_model('identity','Permission');Role=apps.get_model('identity','Role');RolePermission=apps.get_model('identity','RolePermission')
    catalog=[
        ('ai.use','ai','Use approved AI assistants'),('ai.configure','ai','Configure tenant AI providers and policies'),('ai.audit','ai','Audit tenant AI interactions and suggestions'),('ai.knowledge.view','ai','View authorized AI knowledge chunks'),('ai.knowledge.manage','ai','Manage tenant AI knowledge sources'),
        ('workflow.view','workflow','View workflow definitions and instances'),('workflow.manage','workflow','Configure tenant workflows'),('workflow.start','workflow','Start workflows for objects in assigned scope'),('workflow.transition','workflow','Transition workflows in assigned scope')]
    perms={}
    for code,module,description in catalog:
        p,_=Permission.objects.get_or_create(code=code,defaults={'module':module,'name':code.replace('.',' ').title(),'description':description});perms[code]=p
    grants={
        'tenant_admin':list(perms),'grc_manager':list(perms),
        'compliance_manager':['ai.use','ai.knowledge.view','workflow.view','workflow.start','workflow.transition'],
        'risk_manager':['ai.use','ai.knowledge.view','workflow.view','workflow.start','workflow.transition'],
        'control_owner':['ai.use','ai.knowledge.view','workflow.view','workflow.start','workflow.transition'],
        'auditor':['ai.use','ai.audit','ai.knowledge.view','workflow.view','workflow.start','workflow.transition'],
        'viewer':['ai.knowledge.view','workflow.view'],}
    for role_code,codes in grants.items():
        for role in Role.objects.filter(code=role_code):
            for code in codes: RolePermission.objects.get_or_create(role=role,permission=perms[code])
class Migration(migrations.Migration):
    dependencies=[('identity','0005_sprint5_permissions')]
    operations=[migrations.RunPython(add_permissions,migrations.RunPython.noop)]
