from django.db import migrations


def add_framework_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    catalog = [
        ("framework.view", "framework", "View framework library and requirements"),
        ("framework.manage", "framework", "Create and manage tenant frameworks"),
        ("framework.import", "framework", "Import framework content packs"),
        ("framework.mapping.view", "framework", "View requirement crosswalk mappings"),
        ("framework.mapping.manage", "framework", "Create and approve requirement crosswalk mappings"),
    ]
    permissions = {}
    for code, module, description in catalog:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={"module": module, "name": code.replace(".", " ").title(), "description": description})
        permissions[code] = permission

    for role in Role.objects.filter(code="tenant_admin"):
        for permission in permissions.values():
            RolePermission.objects.get_or_create(role=role, permission=permission)
    for role in Role.objects.filter(code="grc_manager"):
        for code in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permissions[code])
    for role in Role.objects.filter(code__in=["auditor", "viewer"]):
        for code in ["framework.view", "framework.mapping.view"]:
            RolePermission.objects.get_or_create(role=role, permission=permissions[code])


class Migration(migrations.Migration):
    dependencies = [("identity", "0001_initial")]
    operations = [migrations.RunPython(add_framework_permissions, migrations.RunPython.noop)]
