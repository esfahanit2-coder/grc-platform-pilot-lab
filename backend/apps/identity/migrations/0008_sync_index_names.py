from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('identity','0007_pilot_connectors_permissions')]
    operations=[
        migrations.RenameIndex(model_name='mfadevice',old_name='identity_mf_user_id_ed8518_idx',new_name='identity_mf_user_id_2ded33_idx'),
        migrations.RenameIndex(model_name='permission',old_name='identity_pe_module_ef8480_idx',new_name='identity_pe_module_bd701c_idx'),
        migrations.RenameIndex(model_name='role',old_name='identity_ro_tenant_4f6959_idx',new_name='identity_ro_tenant__acb795_idx'),
        migrations.RenameIndex(model_name='userrolescope',old_name='identity_us_tenant_29b67b_idx',new_name='identity_us_tenant__214bfe_idx'),
        migrations.RenameIndex(model_name='userrolescope',old_name='identity_us_tenant_59d07a_idx',new_name='identity_us_tenant__faaabb_idx'),
    ]
