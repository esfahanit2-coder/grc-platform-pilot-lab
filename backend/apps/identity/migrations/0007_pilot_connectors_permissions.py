from django.db import migrations
def add_permissions(apps,schema_editor):
    Permission=apps.get_model("identity","Permission");Role=apps.get_model("identity","Role");RolePermission=apps.get_model("identity","RolePermission")
    catalog=[("connector.view","connector","View connector configurations and sync history"),("connector.manage","connector","Manage connector configurations"),("connector.run","connector","Run approved read-only connector collections")]
    perms={}
    for code,module,description in catalog:
        p,_=Permission.objects.get_or_create(code=code,defaults={"module":module,"name":code.replace("."," ").title(),"description":description});perms[code]=p
    grants={"tenant_admin":list(perms),"grc_manager":list(perms),"compliance_manager":["connector.view","connector.run"],"risk_manager":["connector.view","connector.run"],"control_owner":["connector.view","connector.run"],"auditor":["connector.view","connector.run"],"viewer":["connector.view"]}
    for role_code,codes in grants.items():
        for role in Role.objects.filter(code=role_code):
            for code in codes: RolePermission.objects.get_or_create(role=role,permission=perms[code])
class Migration(migrations.Migration):
    dependencies=[("identity","0006_sprint6_ai_workflow_permissions")]
    operations=[migrations.RunPython(add_permissions,migrations.RunPython.noop)]
