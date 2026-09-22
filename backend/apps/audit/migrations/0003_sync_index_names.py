from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('audit','0002_professional_audit_trail')]
    operations=[
        migrations.RenameIndex(model_name='auditevent',old_name='audit_audit_tenant__1e830f_idx',new_name='audit_audit_tenant__290b62_idx'),
        migrations.RenameIndex(model_name='auditevent',old_name='audit_audit_action_249c60_idx',new_name='audit_audit_action_0c0ad1_idx'),
        migrations.RenameIndex(model_name='auditevent',old_name='audit_audit_tenant__b3564d_idx',new_name='audit_audit_tenant__4505e8_idx'),
        migrations.RenameIndex(model_name='auditevent',old_name='audit_audit_tenant__a0a4fc_idx',new_name='audit_audit_tenant__ac5f72_idx'),
    ]
