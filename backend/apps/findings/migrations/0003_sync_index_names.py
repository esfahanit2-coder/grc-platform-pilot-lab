from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('findings','0002_audit_workpaper')]
    operations=[
        migrations.RenameIndex(model_name='finding',old_name='finding_scope_status_idx',new_name='findings_fi_tenant__804a38_idx'),
        migrations.RenameIndex(model_name='finding',old_name='finding_owner_due_idx',new_name='findings_fi_tenant__e2e74e_idx'),
        migrations.RenameIndex(model_name='finding',old_name='finding_severity_idx',new_name='findings_fi_tenant__079339_idx'),
    ]
